/**
 * Studio v4 - The Magic Update 🪄
 * Core Engine: Interactive Canvas + AI Features
 */

// ==========================================
// 1. ENGINE & STATE MANAGEMENT
// ==========================================

const FORMAT_SPECS = {
    'post': { w: 1080, h: 1350, name: 'Post (4:5)' },
    'story': { w: 1080, h: 1920, name: 'Story (9:16)' },
    'square': { w: 1080, h: 1080, name: 'Square (1:1)' }
};

// State
let appState = {
    selectedTemplateId: 'smart_classic',
    bgImage: null,
    bgOpacity: 1.0,     // 0.0 to 1.0
    photoImage: null,
    elements: [],       // List of CanvasObject
    selectedElementId: null,
    isDragging: false,
    isResizing: false,
    dragStart: { x: 0, y: 0, originalSize: 0 },
    history: [],        // Undo stack
    historyIndex: -1,
    format: 'post',     // post, story, square
    width: 1080,
    height: 1350,
    socialIcons: ['instagram', 'facebook', 'x-twitter']  // Active platforms
};

// ==========================================
// 2. TEMPLATE PRESETS (Updated Object Model)
// ==========================================

const TEMPLATE_PRESETS = [
    {
        id: 'smart_classic',
        name: 'SmartEra Classic',
        bg_color: '#0c0f14',
        elements: [
            { type: 'logo_bar', y: 30, brand_text: '@SmartEraPro', color: '#ffffff' },
            { type: 'image_zone', x: 40, y: 150, w: 1000, h: 800, radius: 20 },
            { type: 'text', text: 'Titre principal ici', x: 540, y: 1050, fontSize: 80, color: '#FFD700', align: 'center', font: 'IBM Plex Sans Arabic' }
        ]
    }, {
        id: 'dark_bold',
        name: 'Dark Bold',
        bg_color: '#000000',
        elements: [
            { type: 'logo_bar', y: 40, brand_text: '@SmartEraPro', color: '#ffffff' },
            { type: 'image_zone', x: 0, y: 0, w: 1080, h: 900, radius: 0 }, // Full width top
            { type: 'text', text: 'TITRE ACCROCHEUR', x: 540, y: 950, fontSize: 90, color: '#ffffff', align: 'center', font: 'Rubik' },
            { type: 'shape', x: 40, y: 1150, w: 1000, h: 10, color: '#E50914' } // Red line
        ]
    }, {
        id: 'gold_elegant',
        name: 'Gold Elegant',
        bg_color: '#1a1a1a',
        elements: [
            { type: 'logo_bar', y: 50, brand_text: '@SmartEraPro', color: '#D4AF37' },
            { type: 'image_zone', x: 100, y: 200, w: 880, h: 700, radius: 300 }, // Circle-ish
            { type: 'text', text: 'عنوان فاخر هنا', x: 540, y: 1000, fontSize: 85, color: '#D4AF37', align: 'center', font: 'Amiri' }
        ]
    }
];

// ==========================================
// 3. INTERACTIVE ENGINE CLASS
// ==========================================

class StudioEngine {
    constructor(canvasId) {
        this.canvas = document.getElementById(canvasId);
        this.ctx = this.canvas.getContext('2d');

        // Initial Setup
        this.updateCanvasSize();

        this.initListeners();
        this.loadTemplate('smart_classic');
        this.startLoop();
    }

    updateCanvasSize() {
        this.canvas.width = appState.width;
        this.canvas.height = appState.height;
        // Keep display 100% via CSS, intrinsic size changes
    }

    // --- Core Rendering ---
    startLoop() {
        const loop = () => {
            this.render();
            requestAnimationFrame(loop);
        };
        requestAnimationFrame(loop);
    }

    render() {
        // Clear
        this.ctx.clearRect(0, 0, appState.width, appState.height);

        // 1. Background
        const tpl = TEMPLATE_PRESETS.find(t => t.id === appState.selectedTemplateId) || TEMPLATE_PRESETS[0];
        // Always draw template bg color first
        this.ctx.fillStyle = tpl.bg_color;
        this.ctx.fillRect(0, 0, appState.width, appState.height);

        if (appState.bgImage) {
            this.ctx.save();
            this.ctx.globalAlpha = appState.bgOpacity;
            this.ctx.drawImage(appState.bgImage, 0, 0, appState.width, appState.height);
            this.ctx.restore();
        } else {
            this.drawNoise(this.ctx);
        }
        // Draw Grid if an element is selected (visual feedback)
        if (appState.selectedElementId) this.drawGrid();

        // 2. Render Elements (Z-index order)
        appState.elements.forEach(el => this.drawElement(el));

        // 3. Selection Overlay (if any)
        if (appState.selectedElementId) {
            const el = appState.elements.find(e => e.id === appState.selectedElementId);
            if (el) this.drawSelectionBox(el);
        }
    }

    drawElement(el) {
        this.ctx.save();

        if (el.type === 'image_zone') {
            this.drawImageZone(el);
        } else if (el.type === 'text') {
            this.drawTextElement(el);
        } else if (el.type === 'logo_bar') {
            this.drawLogoBar(el);
        } else if (el.type === 'shape') {
            this.ctx.fillStyle = el.color;
            this.ctx.fillRect(el.x, el.y, el.w, el.h);
        }

        this.ctx.restore();
    }

    drawImageZone(el) {
        // Clip Radius
        this.ctx.beginPath();
        this.ctx.roundRect(el.x, el.y, el.w, el.h, el.radius || 0);
        this.ctx.clip();

        // Draw Image or Placeholder
        if (appState.photoImage) {
            drawCoverImage(this.ctx, appState.photoImage, el.x, el.y, el.w, el.h);
        } else {
            this.ctx.fillStyle = 'rgba(255,255,255,0.1)';
            this.ctx.fillRect(el.x, el.y, el.w, el.h);
            this.ctx.fillStyle = '#ffffff';
            this.ctx.font = '40px sans-serif';
            this.ctx.textAlign = 'center';
            this.ctx.textBaseline = 'middle';
            this.ctx.fillText('📷 Photo Zone', el.x + el.w / 2, el.y + el.h / 2);
        }
    }

    drawTextElement(el) {
        this.ctx.fillStyle = el.color;
        this.ctx.font = `bold ${el.fontSize}px "${el.font}", sans-serif`;
        this.ctx.textAlign = el.align;
        this.ctx.textBaseline = 'top'; // Easier for wrapping

        // Shadow for readability
        this.ctx.shadowColor = 'rgba(0,0,0,0.8)';
        this.ctx.shadowBlur = 10;
        this.ctx.shadowOffsetX = 2;
        this.ctx.shadowOffsetY = 2;

        if (el.text) {
            wrapText(this.ctx, el.text, el.x, el.y, 900, el.fontSize * 1.3);
        }

        // Reset Shadow
        this.ctx.shadowColor = 'transparent';
    }

    drawLogoBar(el) {
        const brandColor = el.color;
        this.ctx.textBaseline = 'middle';

        // Platform icon map (text characters to render on canvas)
        const ICON_MAP = {
            'instagram': { char: '\uf16d', font: '"Font Awesome 6 Brands"' },
            'facebook': { char: '\uf39e', font: '"Font Awesome 6 Brands"' },
            'x-twitter': { char: '\ue61b', font: '"Font Awesome 6 Brands"' },
            'youtube': { char: '\uf167', font: '"Font Awesome 6 Brands"' },
            'tiktok': { char: '\ue07b', font: '"Font Awesome 6 Brands"' },
            'linkedin': { char: '\uf0e1', font: '"Font Awesome 6 Brands"' },
            'snapchat': { char: '\uf2ab', font: '"Font Awesome 6 Brands"' },
            'threads': { char: '\ue618', font: '"Font Awesome 6 Brands"' }
        };

        // Fallback text icons if Font Awesome not available on canvas
        const FALLBACK_MAP = {
            'instagram': '📷',
            'facebook': 'f',
            'x-twitter': '𝕏',
            'youtube': '▶',
            'tiktok': '♪',
            'linkedin': 'in',
            'snapchat': '👻',
            'threads': '@'
        };

        let ix = 40;
        const iconY = el.y + 30;
        const activeIcons = appState.socialIcons || ['instagram', 'facebook', 'x-twitter'];

        activeIcons.forEach(platform => {
            // Draw circle bg
            this.ctx.beginPath();
            this.ctx.arc(ix + 16, iconY, 22, 0, Math.PI * 2);
            this.ctx.fillStyle = 'rgba(255,255,255,0.15)';
            this.ctx.fill();

            // Try Font Awesome icon first
            const iconInfo = ICON_MAP[platform];
            const fallback = FALLBACK_MAP[platform] || '?';

            this.ctx.fillStyle = brandColor;
            this.ctx.textAlign = 'center';

            // Attempt FA Brands font, fall back to text
            if (iconInfo) {
                this.ctx.font = `900 22px ${iconInfo.font}`;
                this.ctx.fillText(iconInfo.char, ix + 16, iconY + 1);

                // Check if it rendered (measure width > 0)
                const m = this.ctx.measureText(iconInfo.char);
                if (m.width < 2) {
                    // Font not loaded yet, use fallback
                    this.ctx.font = 'bold 20px "Space Grotesk", sans-serif';
                    this.ctx.fillText(fallback, ix + 16, iconY + 1);
                }
            } else {
                this.ctx.font = 'bold 20px "Space Grotesk", sans-serif';
                this.ctx.fillText(fallback, ix + 16, iconY + 1);
            }

            ix += 56;
        });

        // Brand Name (editable from input)
        this.ctx.fillStyle = brandColor;
        this.ctx.textAlign = 'left';
        this.ctx.font = 'bold 32px "Space Grotesk", sans-serif';
        this.ctx.fillText(el.brand_text, ix + 10, iconY);
    }

    drawSelectionBox(el) {
        let bounds = this.getBounds(el);
        // Simple bounding box
        this.ctx.strokeStyle = '#00F0FF'; // Neon Blue
        this.ctx.lineWidth = 3;
        this.ctx.setLineDash([10, 5]);
        this.ctx.strokeRect(bounds.x - 10, bounds.y - 10, bounds.w + 20, bounds.h + 20);
        this.ctx.setLineDash([]);

        // Drag Handles (Bottom Right)
        this.ctx.fillStyle = '#ffffff';
        this.ctx.fillRect(bounds.x + bounds.w + 5, bounds.y + bounds.h + 5, 20, 20);
        // Draw icon inside handle?
    }

    resizeCanvas(formatKey) {
        if (!FORMAT_SPECS[formatKey]) return;

        const oldW = appState.width;
        const oldH = appState.height;
        const newSpec = FORMAT_SPECS[formatKey];

        appState.format = formatKey;
        appState.width = newSpec.w;
        appState.height = newSpec.h;
        this.updateCanvasSize(); // Update DOM canvas size

        // Reposition Elements (Auto-Layout)
        const scaleX = newSpec.w / oldW;
        const scaleY = newSpec.h / oldH;

        appState.elements.forEach(el => {
            // Center X relative to new width
            if (el.type === 'text' || el.align === 'center') {
                // If it was centered, keep it centered
                // Simple approach: Scale X
                el.x = el.x * scaleX;
            } else {
                el.x = el.x * scaleX;
            }

            // Scale Y
            el.y = el.y * scaleY;

            // Scale size
            if (el.w) el.w = el.w * scaleX;
            if (el.h) el.h = el.h * scaleY; // Maybe scaleY?
            // if (el.fontSize) el.fontSize = el.fontSize * ((scaleX + scaleY) / 2);
        });

        this.saveHistory();
    }

    drawGrid() {
        this.ctx.save();
        this.ctx.strokeStyle = 'rgba(255, 255, 255, 0.1)';
        this.ctx.lineWidth = 1;
        const GRID = 100; // Visual guide every 100px

        this.ctx.beginPath();
        for (let x = 0; x <= appState.width; x += GRID) {
            this.ctx.moveTo(x, 0);
            this.ctx.lineTo(x, appState.height);
        }
        for (let y = 0; y <= appState.height; y += GRID) {
            this.ctx.moveTo(0, y);
            this.ctx.lineTo(appState.width, y);
        }
        this.ctx.stroke();
        this.ctx.restore();
    }

    drawNoise(ctx) {
        // Optimized noise
        ctx.save();
        ctx.fillStyle = 'rgba(255, 215, 0, 0.05)';
        for (let i = 0; i < 300; i++) {
            ctx.fillRect(Math.random() * appState.width, Math.random() * appState.height, 2, 2);
        }
        ctx.restore();
    }

    // --- State & Logic ---

    loadTemplate(id) {
        const tpl = TEMPLATE_PRESETS.find(t => t.id === id);
        if (!tpl) return;

        appState.selectedTemplateId = id;
        // Deep copy elements to state, adding IDs
        appState.elements = tpl.elements.map((el, i) => ({
            ...el,
            id: `el_${Date.now()}_${i}`
        }));

        // Update UI inputs if needed
        const titleEl = appState.elements.find(e => e.type === 'text');
        if (titleEl) {
            document.getElementById('text-input').value = titleEl.text;
            document.getElementById('text-color').value = titleEl.color;
        }

        this.saveHistory();
    }

    saveHistory() {
        // Remove any "future" history if we were in the middle of the stack
        if (appState.historyIndex < appState.history.length - 1) {
            appState.history = appState.history.slice(0, appState.historyIndex + 1);
        }
        appState.history.push(JSON.stringify(appState.elements));
        appState.historyIndex++;

        // Limit Stack Size
        if (appState.history.length > 50) {
            appState.history.shift();
            appState.historyIndex--;
        }
    }

    undo() {
        if (appState.historyIndex > 0) {
            appState.historyIndex--;
            appState.elements = JSON.parse(appState.history[appState.historyIndex]);
            appState.selectedElementId = null; // Deselect on undo to avoid ghost handles
        }
    }

    redo() {
        if (appState.historyIndex < appState.history.length - 1) {
            appState.historyIndex++;
            appState.elements = JSON.parse(appState.history[appState.historyIndex]);
            appState.selectedElementId = null;
        }
    }

    // --- Interaction ---
    initListeners() {
        this.canvas.addEventListener('mousedown', (e) => this.handleMouseDown(e));
        this.canvas.addEventListener('mousemove', (e) => this.handleMouseMove(e));
        this.canvas.addEventListener('mouseup', (e) => this.handleMouseUp(e));

        // Keyboard Shortcuts
        window.addEventListener('keydown', (e) => {
            if ((e.ctrlKey || e.metaKey) && e.key === 'z') {
                e.preventDefault();
                this.undo();
            }
            if ((e.ctrlKey || e.metaKey) && (e.key === 'y' || (e.shiftKey && e.key === 'Z'))) {
                e.preventDefault();
                this.redo();
            }
            if (e.key === 'Delete' || e.key === 'Backspace') {
                if (appState.selectedElementId) {
                    this.deleteSelected();
                }
            }
        });
    }

    deleteSelected() {
        if (appState.selectedElementId) {
            this.saveHistory(); // Save before deleting
            appState.elements = appState.elements.filter(el => el.id !== appState.selectedElementId);
            appState.selectedElementId = null;
        }
    }

    getCanvasCoords(e) {
        const rect = this.canvas.getBoundingClientRect();
        const scaleX = this.canvas.width / rect.width;
        const scaleY = this.canvas.height / rect.height;
        return {
            x: (e.clientX - rect.left) * scaleX,
            y: (e.clientY - rect.top) * scaleY
        };
    }

    handleMouseDown(e) {
        const coords = this.getCanvasCoords(e);
        const hitX = coords.x;
        const hitY = coords.y;

        // 1. Check Resize Handle of Selected Element first
        if (appState.selectedElementId) {
            const el = appState.elements.find(e => e.id === appState.selectedElementId);
            const bounds = this.getBounds(el);
            // Handle is at bottom-right (bounds.x + bounds.w, bounds.y + bounds.h)
            const hx = bounds.x + bounds.w;
            const hy = bounds.y + bounds.h;

            // 30px hit zone for handle (offset by the padding drawn in drawSelectionBox)
            if (Math.abs(hitX - (hx + 10)) < 40 && Math.abs(hitY - (hy + 10)) < 40) {
                appState.isResizing = true;
                appState.dragStart = { x: hitX, y: hitY, originalSize: el.type === 'text' ? el.fontSize : el.w };
                return;
            }
        }

        // 2. HIT TEST Elements
        let hitElement = null;
        for (let i = appState.elements.length - 1; i >= 0; i--) {
            const el = appState.elements[i];
            if (this.isHit(el, hitX, hitY)) {
                hitElement = el;
                break;
            }
        }

        if (hitElement) {
            appState.selectedElementId = hitElement.id;
            appState.isDragging = true;
            appState.dragStart = { x: hitX - hitElement.x, y: hitY - hitElement.y };

            // Sync UI
            if (hitElement.type === 'text') {
                document.getElementById('text-input').value = hitElement.text;
                document.getElementById('text-color').value = hitElement.color;
            }
        } else {
            appState.selectedElementId = null;
        }
    }

    handleMouseMove(e) {
        const coords = this.getCanvasCoords(e);

        // RESIZE LOGIC
        if (appState.isResizing && appState.selectedElementId) {
            const el = appState.elements.find(e => e.id === appState.selectedElementId);
            if (el) {
                const dx = coords.x - appState.dragStart.x;

                if (el.type === 'text') {
                    // Scale font size
                    const newSize = appState.dragStart.originalSize + (dx * 0.5);
                    el.fontSize = Math.max(20, newSize);
                } else if (el.type === 'image_zone' || el.type === 'shape') {
                    // Scale width
                    el.w = Math.max(100, appState.dragStart.originalSize + dx);
                }
                this.canvas.style.cursor = 'nwse-resize';
            }
            return;
        }

        // DRAG LOGIC
        if (appState.isDragging && appState.selectedElementId) {
            const el = appState.elements.find(e => e.id === appState.selectedElementId);
            if (el) {
                let newX = coords.x - appState.dragStart.x;
                let newY = coords.y - appState.dragStart.y;

                // Simple Snap-to-Grid (Grid Size 20px)
                const GRID_SIZE = 20;
                if (!e.shiftKey) { // Hold Shift to disable snapping
                    newX = Math.round(newX / GRID_SIZE) * GRID_SIZE;
                    newY = Math.round(newY / GRID_SIZE) * GRID_SIZE;
                }

                el.x = newX;
                el.y = newY;
                this.canvas.style.cursor = 'move';
            }
            return;
        }

        // HOVER CURSOR
        this.updateCursor(coords);
    }

    handleMouseUp(e) {
        if (appState.isDragging || appState.isResizing) {
            this.saveHistory();
        }
        appState.isDragging = false;
        appState.isResizing = false;
    }

    updateCursor(coords) {
        if (appState.selectedElementId) {
            const el = appState.elements.find(e => e.id === appState.selectedElementId);
            const bounds = this.getBounds(el);
            const hx = bounds.x + bounds.w + 10;
            const hy = bounds.y + bounds.h + 10;
            if (Math.abs(coords.x - hx) < 30 && Math.abs(coords.y - hy) < 30) {
                this.canvas.style.cursor = 'nwse-resize';
                return;
            }
        }

        for (let i = appState.elements.length - 1; i >= 0; i--) {
            if (this.isHit(appState.elements[i], coords.x, coords.y)) {
                this.canvas.style.cursor = 'move';
                return;
            }
        }
        this.canvas.style.cursor = 'default';
    }

    isHit(el, x, y) {
        if (el.type === 'image_zone' || el.type === 'shape') {
            return (x >= el.x && x <= el.x + el.w && y >= el.y && y <= el.y + el.h);
        }
        if (el.type === 'text') {
            const bounds = this.getBounds(el);
            return (x >= bounds.x && x <= bounds.x + bounds.w && y >= bounds.y && y <= bounds.y + bounds.h);
        }
        if (el.type === 'logo_bar') {
            return (y >= el.y && y <= el.y + 80);
        }
        return false;
    }

    getBounds(el) {
        if (!el) return { x: 0, y: 0, w: 0, h: 0 };
        if (el.type === 'text') {
            this.ctx.font = `bold ${el.fontSize}px "${el.font}", sans-serif`;
            const metrics = this.ctx.measureText(el.text);
            let lx = el.x;
            if (el.align === 'center') lx = el.x - metrics.width / 2;
            else if (el.align === 'right') lx = el.x - metrics.width;
            return { x: lx, y: el.y, w: metrics.width, h: el.fontSize * 1.5 }; // 1.5 lineHeight
        }
        return { x: el.x, y: el.y, w: el.w, h: el.h || 100 };
    }
}

// ==========================================
// 4. GLOBAL HELPERS & EXPORTS
// ==========================================

let engine = null;

document.addEventListener('DOMContentLoaded', () => {
    engine = new StudioEngine('live-canvas');
    initUI();
});

// ==========================================
// 5. TEMPLATE MANAGER (LocalStorage)
// ==========================================

function getSavedTemplates() {
    try {
        const raw = localStorage.getItem('studio_templates');
        return raw ? JSON.parse(raw) : [];
    } catch (e) {
        console.error("Error loading templates", e);
        return [];
    }
}

function saveTemplate() {
    const name = prompt("Enter a name for this template:", "My Cool Design");
    if (!name) return;

    const newTpl = {
        id: 'user_' + Date.now(),
        name: name,
        created_at: new Date().toISOString(),
        state: appState // Save the entire state
    };

    const saved = getSavedTemplates();
    saved.unshift(newTpl); // Add to top
    localStorage.setItem('studio_templates', JSON.stringify(saved));

    // Re-render strip
    initUI(); // simpler to just re-init or we can extract renderTemplateStrip

    // Show toast (simple alert for now)
    // alert("Template saved!"); 
    // Better: quick visual feedback?
    const btn = document.querySelector('.fa-floppy-disk').parentElement;
    const ogHtml = btn.innerHTML;
    btn.innerHTML = '<i class="fa-solid fa-check" style="color:var(--primary)"></i>';
    setTimeout(() => btn.innerHTML = ogHtml, 2000);
}

function deleteTemplate(id) {
    const saved = getSavedTemplates().filter(t => t.id !== id);
    localStorage.setItem('studio_templates', JSON.stringify(saved));
    initUI();
}

// Make globally available
window.saveTemplate = saveTemplate;
window.deleteTemplate = deleteTemplate;

// Extracted for re-use
function renderTemplateStrip() {
    // Template Strip
    const strip = document.getElementById('template-strip');
    if (strip) {
        strip.innerHTML = '';

        // 1. Render User Saved Templates
        const saved = getSavedTemplates();
        if (saved.length > 0) {
            // Label or separator could go here
            saved.forEach(tpl => {
                const div = document.createElement('div');
                div.className = 'tpl-item';
                div.innerHTML = `<span style="color:var(--primary)">★</span> ${tpl.name}`;
                div.title = "Right-click to delete";

                div.onclick = () => {
                    // Load saved state
                    if (tpl.state) {
                        // Restore state
                        appState = JSON.parse(JSON.stringify(tpl.state));
                        // Re-hook images if needed (images might be broken if blobs, but URLs work)
                        // For MVP assuming standard assets. 
                        // We need to re-render.
                        engine.render();
                        // Update UI inputs to match state
                        const tInput = document.getElementById('text-input');
                        const brandInput = document.getElementById('brand-input');
                        const textEl = appState.elements.find(e => e.type === 'text');
                        const logoEl = appState.elements.find(e => e.type === 'logo_bar');

                        if (tInput && textEl) tInput.value = textEl.text;
                        if (brandInput && logoEl) brandInput.value = logoEl.brand_text;

                        // Update Social Icons UI
                        if (appState.socialIcons) {
                            document.querySelectorAll('.social-chip').forEach(chip => {
                                const platform = chip.dataset.platform;
                                const active = appState.socialIcons.includes(platform);
                                if (active) chip.classList.add('active');
                                else chip.classList.remove('active');
                                const chk = chip.querySelector('input');
                                if (chk) chk.checked = active;
                            });
                        }
                    } else {
                        engine.loadTemplate(tpl.id);
                    }

                    strip.querySelectorAll('.tpl-item').forEach(d => d.classList.remove('active'));
                    div.classList.add('active');
                };

                // Right click to delete
                div.oncontextmenu = (e) => {
                    e.preventDefault();
                    if (confirm(`Delete template "${tpl.name}"?`)) {
                        deleteTemplate(tpl.id);
                    }
                };

                strip.appendChild(div);
            });

            // Divider
            const divider = document.createElement('div');
            divider.style.width = '1px';
            divider.style.background = 'var(--border)';
            divider.style.margin = '0 4px';
            strip.appendChild(divider);
        }

        // 2. Render System Presets
        TEMPLATE_PRESETS.forEach(tpl => {
            const div = document.createElement('div');
            div.className = 'tpl-item';
            div.textContent = tpl.name;
            div.onclick = () => {
                engine.loadTemplate(tpl.id);
                strip.querySelectorAll('.tpl-item').forEach(d => d.classList.remove('active'));
                div.classList.add('active');
            };
            strip.appendChild(div);
        });

        // Set first as active if none selected
        if (!strip.querySelector('.active') && strip.firstChild) {
            strip.firstChild.classList.add('active');
        }
    }
}

function initUI() {
    renderTemplateStrip();

    // Format Select
    const fmtSelect = document.getElementById('format-select');
    if (fmtSelect) {
        fmtSelect.addEventListener('change', (e) => {
            engine.resizeCanvas(e.target.value);
        });
    }

    // Hook / Title Input
    const tInput = document.getElementById('text-input');
    if (tInput) {
        tInput.addEventListener('input', (e) => {
            const el = appState.elements.find(x => x.type === 'text');
            if (el) el.text = e.target.value;
        });
    }

    // Text Color
    const cInput = document.getElementById('text-color');
    if (cInput) {
        cInput.addEventListener('input', (e) => {
            const el = appState.elements.find(x => x.type === 'text');
            if (el) el.color = e.target.value;
            const label = document.getElementById('color-label');
            if (label) label.textContent = e.target.value.toUpperCase();
        });
    }

    // Brand / Page Name Input
    const brandInput = document.getElementById('brand-input');
    if (brandInput) {
        brandInput.addEventListener('input', (e) => {
            const logoEl = appState.elements.find(x => x.type === 'logo_bar');
            if (logoEl) logoEl.brand_text = e.target.value;
        });
    }

    // BG Intensity Slider
    const bgSlider = document.getElementById('bg-intensity');
    const bgValue = document.getElementById('bg-intensity-value');
    const bgWrap = document.getElementById('bg-intensity-wrap');
    if (bgSlider) {
        bgSlider.addEventListener('input', (e) => {
            appState.bgOpacity = parseInt(e.target.value) / 100;
            if (bgValue) bgValue.textContent = e.target.value + '%';
        });
    }

    // Social Icons Picker
    const socialPicker = document.getElementById('social-icons-picker');
    if (socialPicker) {
        socialPicker.querySelectorAll('.social-chip').forEach(chip => {
            chip.addEventListener('click', (e) => {
                e.preventDefault();
                const checkbox = chip.querySelector('input[type="checkbox"]');
                checkbox.checked = !checkbox.checked;
                chip.classList.toggle('active', checkbox.checked);

                // Rebuild socialIcons array from checked chips
                const active = [];
                socialPicker.querySelectorAll('.social-chip').forEach(c => {
                    if (c.querySelector('input').checked) {
                        active.push(c.dataset.platform);
                    }
                });
                appState.socialIcons = active;
            });
        });
    }
}

function triggerMagic() {
    showToast('✨ Analyzing canvas with AI...', 'info');
    // TODO: Connect to backend Gemini API
    setTimeout(() => {
        showToast('🪄 Magic suggestions ready!', 'success');
    }, 1500);
}

window.handleBgUpload = (e) => {
    const file = e.target.files[0];
    if (!file) return;
    const img = new Image();
    img.onload = () => {
        appState.bgImage = img;
        // Show intensity slider
        const wrap = document.getElementById('bg-intensity-wrap');
        if (wrap) wrap.style.display = 'block';
    };
    img.src = URL.createObjectURL(file);
};

window.handlePhotoUpload = (e) => {
    const file = e.target.files[0];
    if (!file) return;
    const img = new Image();
    img.onload = () => { appState.photoImage = img; };
    img.src = URL.createObjectURL(file);
};

window.exportCanvas = () => {
    const link = document.createElement('a');
    link.download = `studio_magic_${Date.now()}.png`;
    link.href = document.getElementById('live-canvas').toDataURL('image/png');
    link.click();
    showToast('Exported ✅', 'success');
};


// --- Utils ---

function wrapText(ctx, text, x, y, maxWidth, lineHeight) {
    const words = text.split(' ');
    let line = '';

    for (let n = 0; n < words.length; n++) {
        const testLine = line + words[n] + ' ';
        const metrics = ctx.measureText(testLine);
        const testWidth = metrics.width;
        if (testWidth > maxWidth && n > 0) {
            ctx.fillText(line, x, y);
            line = words[n] + ' ';
            y += lineHeight;
        } else {
            line = testLine;
        }
    }
    ctx.fillText(line, x, y);
}

function drawCoverImage(ctx, img, x, y, w, h) {
    const scale = Math.max(w / img.width, h / img.height);
    const nw = img.width * scale;
    const nh = img.height * scale;
    const nx = x + (w - nw) / 2;
    const ny = y + (h - nh) / 2;
    ctx.drawImage(img, nx, ny, nw, nh);
}

function showToast(msg, type = 'info') {
    let c = document.getElementById('toast-container');
    if (!c) {
        c = document.createElement('div');
        c.id = 'toast-container';
        c.style.cssText = 'position:fixed;top:1rem;right:1rem;z-index:9999;display:flex;flex-direction:column;gap:0.4rem;pointer-events:none;';
        document.body.appendChild(c);
    }
    const t = document.createElement('div');
    t.className = `toast ${type}`;
    t.textContent = msg;
    t.style.cssText = 'pointer-events:auto;padding:12px 24px;background:#333;color:#fff;border-radius:8px;box-shadow:0 4px 12px rgba(0,0,0,0.3);';
    if (type === 'success') t.style.background = '#00F0FF';
    if (type === 'success') t.style.color = '#000';

    c.appendChild(t);
    setTimeout(() => t.remove(), 3000);
}
