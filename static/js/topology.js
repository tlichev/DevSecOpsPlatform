/**
 * NetOps Platform — Animated SVG Network Topology Map
 * Renders the 3-site enterprise topology with live status pulsing.
 */

'use strict';

class NetworkTopology {
    constructor(containerId) {
        this.el = document.getElementById(containerId);
        if (!this.el) return;

        this.W = 900;
        this.H = 480;

        // ── Layout positions (absolute, within 900x480 viewBox) ──────────
        this.nodes = {
            isp: {
                id: 'isp', x: 450, y: 95,
                label: 'ISP Core', sublabel: 'WAN Core',
                color: '#f59e0b', radius: 36,
                url: null, type: 'cloud',
            },
            sofia: {
                id: 'sofia', x: 155, y: 285,
                label: 'SOFIA', sublabel: '4.2.2.0/27',
                color: '#10b981', radius: 58,
                url: '/sites/sofia/', type: 'site',
            },
            burgas: {
                id: 'burgas', x: 745, y: 285,
                label: 'BURGAS', sublabel: '4.2.2.64/27',
                color: '#3b82f6', radius: 58,
                url: '/sites/burgas/', type: 'site',
            },
            plovdiv: {
                id: 'plovdiv', x: 450, y: 400,
                label: 'PLOVDIV', sublabel: '4.2.2.32/27',
                color: '#a855f7', radius: 58,
                url: '/sites/plovdiv/', type: 'site',
            },
        };

        // ── Per-site device dots (offset from site center) ────────────────
        this.devices = {
            // Sofia
            sofia_prim: { site: 'sofia', label: 'PRIM', dx: -28, dy: -22, url: '/inventory/?site=sofia&role=firewall_primary' },
            sofia_sec:  { site: 'sofia', label: 'SEC',  dx:  28, dy: -22, url: '/inventory/?site=sofia&role=firewall_secondary' },
            sofia_sw:   { site: 'sofia', label: 'SW',   dx: -28, dy:  22, url: '/inventory/?site=sofia&role=l2_switch' },
            sofia_r:    { site: 'sofia', label: 'RTR',  dx:  28, dy:  22, url: '/inventory/?site=sofia&role=router' },
            // Burgas
            burgas_prim: { site: 'burgas', label: 'PRIM', dx: -28, dy: -22, url: '/inventory/?site=burgas&role=firewall_primary' },
            burgas_sec:  { site: 'burgas', label: 'SEC',  dx:  28, dy: -22, url: '/inventory/?site=burgas&role=firewall_secondary' },
            burgas_sw:   { site: 'burgas', label: 'SW',   dx: -28, dy:  22, url: '/inventory/?site=burgas&role=l2_switch' },
            burgas_r:    { site: 'burgas', label: 'RTR',  dx:  28, dy:  22, url: '/inventory/?site=burgas&role=router' },
            // Plovdiv
            plovdiv_prim: { site: 'plovdiv', label: 'PRIM', dx: -30, dy: -18, url: '/inventory/?site=plovdiv&role=firewall_primary' },
            plovdiv_sec:  { site: 'plovdiv', label: 'SEC',  dx:  30, dy: -18, url: '/inventory/?site=plovdiv&role=firewall_secondary' },
            plovdiv_sw:   { site: 'plovdiv', label: 'SW',   dx: -30, dy:  18, url: '/inventory/?site=plovdiv&role=l2_switch' },
            plovdiv_r:    { site: 'plovdiv', label: 'RTR',  dx:  30, dy:  18, url: '/inventory/?site=plovdiv&role=router' },
        };

        // ── Connection paths between sites ────────────────────────────────
        this.connections = [
            { from: 'sofia',   to: 'isp',    wan: '4.2.2.2 → 4.2.2.1',  bw: '1Gbps' },
            { from: 'burgas',  to: 'isp',    wan: '4.2.2.66 → 4.2.2.1', bw: '1Gbps' },
            { from: 'plovdiv', to: 'isp',    wan: '4.2.2.34 → 4.2.2.1', bw: '1Gbps' },
        ];

        // status map: device-id → 'up' | 'down' | 'unknown'
        this.statusMap = {};

        this._build();
        this._fetchStatus();
        setInterval(() => this._fetchStatus(), 30000);
    }

    // ── Build SVG ──────────────────────────────────────────────────────────
    _build() {
        const svg = this._svgEl('svg', {
            viewBox: `0 0 ${this.W} ${this.H}`,
            width: '100%',
            height: '100%',
            class: 'topology-canvas',
        });

        // Defs: glow filter + animated gradient
        svg.appendChild(this._buildDefs());

        // Background grid dots
        svg.appendChild(this._buildGrid());

        // Connection lines (below nodes)
        const connGroup = this._svgEl('g', { class: 'connections' });
        this.connections.forEach(c => connGroup.appendChild(this._buildConnection(c)));
        svg.appendChild(connGroup);

        // Site nodes
        const nodeGroup = this._svgEl('g', { class: 'site-nodes' });
        Object.values(this.nodes).forEach(n => nodeGroup.appendChild(this._buildNode(n)));
        svg.appendChild(nodeGroup);

        // Device dots
        const devGroup = this._svgEl('g', { class: 'device-dots' });
        Object.entries(this.devices).forEach(([id, d]) => devGroup.appendChild(this._buildDevice(id, d)));
        svg.appendChild(devGroup);

        this.svg = svg;
        this.el.innerHTML = '';
        this.el.appendChild(svg);
    }

    _buildDefs() {
        const defs = this._svgEl('defs');
        const colors = { blue: '#3b82f6', green: '#10b981', amber: '#f59e0b', purple: '#a855f7' };
        Object.entries(colors).forEach(([name, color]) => {
            const f = this._svgEl('filter', { id: `glow-${name}`, x: '-30%', y: '-30%', width: '160%', height: '160%' });
            const fe = this._svgEl('feDropShadow', {
                dx: '0', dy: '0', stdDeviation: '4', 'flood-color': color, 'flood-opacity': '0.8',
            });
            f.appendChild(fe);
            defs.appendChild(f);
        });
        // Animated dash pattern for connections
        const mk = this._svgEl('marker', {
            id: 'arrow', viewBox: '0 0 8 8', refX: '7', refY: '4',
            markerWidth: '6', markerHeight: '6', orient: 'auto-start-reverse',
        });
        const path = this._svgEl('path', { d: 'M0,0 L8,4 L0,8 Z', fill: '#3b82f6', opacity: '0.7' });
        mk.appendChild(path);
        defs.appendChild(mk);
        return defs;
    }

    _buildGrid() {
        const g = this._svgEl('g', { class: 'bg-grid', opacity: '0.07' });
        for (let x = 0; x <= this.W; x += 40) {
            const line = this._svgEl('line', { x1: x, y1: 0, x2: x, y2: this.H, stroke: '#3b82f6', 'stroke-width': '0.5' });
            g.appendChild(line);
        }
        for (let y = 0; y <= this.H; y += 40) {
            const line = this._svgEl('line', { x1: 0, y1: y, x2: this.W, y2: y, stroke: '#3b82f6', 'stroke-width': '0.5' });
            g.appendChild(line);
        }
        return g;
    }

    _buildConnection(conn) {
        const from = this.nodes[conn.from];
        const to   = this.nodes[conn.to];
        const g = this._svgEl('g', { class: `conn conn-${conn.from}` });

        // Main path (cubic bezier for smooth curve)
        const mx = (from.x + to.x) / 2;
        const my = (from.y + to.y) / 2 - 20;
        const d  = `M${from.x},${from.y} Q${mx},${my} ${to.x},${to.y}`;

        // Glow underlay
        const glow = this._svgEl('path', {
            d, fill: 'none',
            stroke: '#3b82f6', 'stroke-width': '8', opacity: '0.08',
        });
        g.appendChild(glow);

        // Main line
        const line = this._svgEl('path', {
            d, fill: 'none',
            stroke: '#3b82f6', 'stroke-width': '1.5',
            'stroke-dasharray': '6 4', opacity: '0.55',
            class: 'conn-line',
        });
        g.appendChild(line);

        // Animated traffic dot
        const dot = this._svgEl('circle', { r: '3', fill: '#3b82f6', opacity: '0.9' });
        const anim = this._svgEl('animateMotion', {
            dur: `${2.5 + Math.random() * 2}s`,
            repeatCount: 'indefinite',
            keyTimes: '0;1',
            calcMode: 'linear',
        });
        const mp = this._svgEl('mpath', {});
        mp.setAttributeNS('http://www.w3.org/1999/xlink', 'href', '');
        // Use path directly
        anim.setAttribute('path', d);
        dot.appendChild(anim);
        g.appendChild(dot);

        // Reverse dot
        const dot2 = this._svgEl('circle', { r: '3', fill: '#60a5fa', opacity: '0.7' });
        const anim2 = this._svgEl('animateMotion', {
            dur: `${3 + Math.random() * 2}s`,
            repeatCount: 'indefinite',
            keyTimes: '0;1',
            calcMode: 'linear',
            keyPoints: '1;0',
        });
        anim2.setAttribute('path', d);
        dot2.appendChild(anim2);
        g.appendChild(dot2);

        // Label
        const label = this._svgEl('text', {
            x: mx, y: my - 6,
            'text-anchor': 'middle',
            fill: '#374151',
            'font-size': '10',
            'font-family': 'JetBrains Mono, monospace',
        });
        label.textContent = conn.bw;
        g.appendChild(label);

        return g;
    }

    _buildNode(node) {
        const g = this._svgEl('g', {
            class: `site-node site-${node.id}`,
            transform: `translate(${node.x},${node.y})`,
            style: node.url ? 'cursor:pointer' : '',
        });
        if (node.url) {
            g.addEventListener('click', () => window.location.href = node.url);
            g.addEventListener('mouseenter', () => pulseRing.setAttribute('opacity', '1'));
            g.addEventListener('mouseleave', () => pulseRing.setAttribute('opacity', '0.5'));
        }

        const glowId = node.color === '#f59e0b' ? 'glow-amber'
                     : node.color === '#10b981' ? 'glow-green'
                     : node.color === '#3b82f6' ? 'glow-blue'
                     : 'glow-purple';

        // Outer pulse ring
        const pulseRing = this._svgEl('circle', {
            r: node.radius + 18, cx: '0', cy: '0',
            fill: 'none', stroke: node.color,
            'stroke-width': '1.5', opacity: '0.5',
            class: 'pulse-ring',
        });
        // Animate pulse
        const pulseAnim = this._svgEl('animate', {
            attributeName: 'r',
            values: `${node.radius + 12};${node.radius + 24};${node.radius + 12}`,
            dur: '2.8s', repeatCount: 'indefinite', calcMode: 'ease',
        });
        const pulseAlpha = this._svgEl('animate', {
            attributeName: 'opacity',
            values: '0.5;0.1;0.5', dur: '2.8s', repeatCount: 'indefinite',
        });
        pulseRing.appendChild(pulseAnim);
        pulseRing.appendChild(pulseAlpha);
        g.appendChild(pulseRing);

        // Main circle
        const circle = this._svgEl('circle', {
            r: node.radius, cx: '0', cy: '0',
            fill: `${node.color}1a`, stroke: node.color,
            'stroke-width': '2', filter: `url(#${glowId})`,
        });
        g.appendChild(circle);

        if (node.type === 'cloud') {
            // Cloud icon
            const icon = this._svgEl('text', {
                x: '0', y: '8',
                'text-anchor': 'middle',
                fill: node.color, 'font-size': '22',
            });
            icon.textContent = '☁';
            g.appendChild(icon);
        } else {
            // Network icon
            const icon = this._svgEl('text', {
                x: '0', y: '-4',
                'text-anchor': 'middle',
                fill: node.color, 'font-size': '18',
            });
            icon.textContent = '⬡';
            g.appendChild(icon);
        }

        // Label
        const lbl = this._svgEl('text', {
            x: '0', y: node.radius + 18,
            'text-anchor': 'middle',
            fill: node.color,
            'font-size': '12', 'font-weight': '700',
            'font-family': 'Inter, sans-serif',
            'letter-spacing': '1',
        });
        lbl.textContent = node.label;
        g.appendChild(lbl);

        // Sublabel
        const sub = this._svgEl('text', {
            x: '0', y: node.radius + 32,
            'text-anchor': 'middle',
            fill: '#6b7280', 'font-size': '10',
            'font-family': 'JetBrains Mono, monospace',
        });
        sub.textContent = node.sublabel;
        g.appendChild(sub);

        return g;
    }

    _buildDevice(id, dev) {
        const site = this.nodes[dev.site];
        const cx = site.x + dev.dx;
        const cy = site.y + dev.dy;
        const color = site.color;

        const g = this._svgEl('g', {
            class: `device-dot device-${id}`,
            style: 'cursor:pointer',
            transform: `translate(${cx},${cy})`,
        });
        g.addEventListener('click', (e) => {
            e.stopPropagation();
            if (dev.url) window.location.href = dev.url;
        });

        // Dot background
        const dot = this._svgEl('circle', {
            r: '7', cx: '0', cy: '0',
            fill: '#111827', stroke: color, 'stroke-width': '1.5',
        });
        g.appendChild(dot);

        // Status fill (updated by fetchStatus)
        const fill = this._svgEl('circle', {
            r: '4', cx: '0', cy: '0',
            fill: color,
            class: `device-fill device-fill-${id}`,
        });
        g.appendChild(fill);

        // Tooltip label
        const title = this._svgEl('title');
        title.textContent = `${id.toUpperCase()} — ${dev.label}`;
        g.appendChild(title);

        return g;
    }

    // ── Status fetch ───────────────────────────────────────────────────────
    _fetchStatus() {
        fetch('/api/devices/status/', {
            headers: { 'Accept': 'application/json' },
            credentials: 'same-origin',
        })
        .then(r => r.ok ? r.json() : null)
        .then(data => { if (data) this._applyStatus(data); })
        .catch(() => { /* API not ready yet — dots stay default color */ });
    }

    _applyStatus(data) {
        const colorMap = { up: '#10b981', down: '#ef4444', unknown: '#6b7280' };
        data.forEach(item => {
            const key   = `${item.site}_${item.role_short}`;
            const fills = this.svg.querySelectorAll(`.device-fill-${key}`);
            fills.forEach(el => {
                el.setAttribute('fill', colorMap[item.status] || colorMap.unknown);
                if (item.status === 'down') {
                    el.setAttribute('opacity', '0.7');
                }
            });
        });
    }

    // ── SVG helper ─────────────────────────────────────────────────────────
    _svgEl(tag, attrs = {}) {
        const el = document.createElementNS('http://www.w3.org/2000/svg', tag);
        Object.entries(attrs).forEach(([k, v]) => el.setAttribute(k, v));
        return el;
    }
}

// ── Init on DOM ready ───────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
    if (document.getElementById('topology-map')) {
        window._topology = new NetworkTopology('topology-map');
    }
});
