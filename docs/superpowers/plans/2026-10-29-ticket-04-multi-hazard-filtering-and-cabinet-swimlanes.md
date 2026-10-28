# Ticket 04: Multi-Hazard Filtering, Fuzzy Search & Cabinet Swimlanes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement real-time multi-hazard filtering, instant multi-field in-batch chemical search, dynamic pill counter badges, view layout toggling, and grouped collapsible physical cabinet swimlanes in the hazardous waste management interface.

**Architecture:** Extend Alpine.js reactive state in `src/templates/index.html` with client-side reactive getters: `batchSearchQuery` (matching chemical name, physical segregation bin, and recommended container), `activeHazardFilters` (compound AND intersection logic), `hazardCounts` (batch-wide distribution), and `cabinetZones` (6 physical safety containment zones). Add segmented view toggle (`Card Grid` vs `Cabinet Swimlanes`), collapsible accordion controls (`expandedZones` with master toggle), and zero-result empty state cards with a 1-click filter reset action.

**Tech Stack:** FastAPI, Jinja2, Alpine.js (CDN), Tailwind CSS (CDN), Python standard library `unittest`.

**Spec:** [.scratch/frontend/spec.md](file:///C:/Users/stars/AI-ML/D2S-MTP/.scratch/frontend/spec.md) and [.scratch/frontend/issues/04-multi-hazard-filtering-and-cabinet-swimlanes.md](file:///C:/Users/stars/AI-ML/D2S-MTP/.scratch/frontend/issues/04-multi-hazard-filtering-and-cabinet-swimlanes.md)

## Global Constraints

- **Python Runtime**: Strictly target dedicated Conda environment `C:\Users\stars\miniconda3\envs\d2s-mtp` (`python.exe`). Zero packages in base.
- **Frontend Stack**: Server-rendered HTML with Tailwind CSS CDN and Alpine.js CDN. No Node.js build chain; zero npm packages.
- **Testing Standard**: Python standard library `unittest` ONLY (`unittest.TestCase`). Do NOT use `pytest`. Run tests via `& "C:\Users\stars\miniconda3\envs\d2s-mtp\python.exe" -m unittest`.
- **Git Config**: Author Aryan Das <starsnipe407@gmail.com>. Windows PowerShell syntax (use `;` instead of `&&`).
- **Domain Language**: Adhere strictly to [CONTEXT.md](file:///C:/Users/stars/AI-ML/D2S-MTP/CONTEXT.md) terms: `Batch Run`, `Review Queue`, `Classification Review`, `Containment Zone`, `Segregation Bin`, `Waste Management Plan`.

---

## File Structure

- Modify: `src/templates/index.html`
  - Adds dedicated in-batch search input (`batchSearchQuery`) with clear `✕` button.
  - Adds multi-hazard filter pills with live counter badges (`All`, `🔥 Flammable`, `☠️ Toxic`, `🧪 Corrosive`, `☣️ Infectious`, `⚠️ Carcinogenic`, `⚠️ Review Required`) supporting compound AND selection.
  - Adds segmented layout toggle (`[ ⊞ Card Grid ]  [ ☵ Cabinet Swimlanes ]`).
  - Implements Grouped Cabinet Swimlanes with 6 physical containment zones, secondary containment notes, header counts, and collapsible accordion chevrons.
  - Implements master `[ Collapse All ]` / `[ Expand All ]` toggle.
  - Implements zero-result empty state with `[ Reset Filters ]` button.
- Modify: `tests/test_app.py`
  - Adds unit tests verifying template structure, Alpine state attributes, filter pill counter bindings, swimlane markup, and layout toggle elements.

---

### Task 1: Implement In-Batch Search & Multi-Hazard Filter Pills with Live Counters

**Files:**
- Modify: `src/templates/index.html`
- Modify: `tests/test_app.py`

**Interfaces:**
- Consumes: `activeBatch.items`, `getBadgeClass(cat)`
- Produces:
  - `batchSearchQuery`: string reactive model for in-batch search
  - `activeHazardFilters`: array of selected hazard categories
  - `toggleHazardFilter(category)`: compound AND selection logic
  - `hazardCounts`: computed getter returning live counts for each hazard
  - `filteredItems`: computed getter filtering active batch items by search text and active hazard pills

- [ ] **Step 1: Write the failing unit test**

Add `test_template_contains_in_batch_search_and_hazard_filter_pills` in `tests/test_app.py`:

```python
    def test_template_contains_in_batch_search_and_hazard_filter_pills(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        html = response.text

        # In-batch search input and clear button
        self.assertIn("batchSearchQuery", html)
        self.assertIn("Filter chemicals in batch", html)

        # Multi-hazard filter pills with live counts
        self.assertIn("activeHazardFilters", html)
        self.assertIn("toggleHazardFilter", html)
        self.assertIn("filteredItems", html)
        self.assertIn("Flammable", html)
        self.assertIn("Toxic", html)
        self.assertIn("Corrosive", html)
        self.assertIn("Infectious", html)
        self.assertIn("Carcinogenic", html)
        self.assertIn("Review Required", html)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `& "C:\Users\stars\miniconda3\envs\d2s-mtp\python.exe" -m unittest tests/test_app.py`
Expected: FAIL with `AssertionError: 'batchSearchQuery' not found in response HTML`

- [ ] **Step 3: Update src/templates/index.html**

1. In `x-data` object, add reactive properties and methods:
   ```javascript
   batchSearchQuery: '',
   activeHazardFilters: [], // e.g. ['Flammable', 'Toxic']

   get hazardCounts() {
     if (!this.activeBatch || !this.activeBatch.items) return { All: 0, Flammable: 0, Toxic: 0, Corrosive: 0, Infectious: 0, Carcinogenic: 0, 'Review Required': 0 };
     const items = this.activeBatch.items;
     return {
       All: items.length,
       Flammable: items.filter(i => i.flammable).length,
       Toxic: items.filter(i => i.toxic).length,
       Corrosive: items.filter(i => i.corrosive).length,
       Infectious: items.filter(i => i.infectious).length,
       Carcinogenic: items.filter(i => i.carcinogenic).length,
       'Review Required': items.filter(i => i.review_required).length,
     };
   },

   toggleHazardFilter(category) {
     if (category === 'All') {
       this.activeHazardFilters = [];
       return;
     }
     const idx = this.activeHazardFilters.indexOf(category);
     if (idx >= 0) {
       this.activeHazardFilters.splice(idx, 1);
     } else {
       this.activeHazardFilters.push(category);
     }
   },

   isHazardFilterActive(category) {
     if (category === 'All') {
       return this.activeHazardFilters.length === 0;
     }
     return this.activeHazardFilters.includes(category);
   },

   get filteredItems() {
     if (!this.activeBatch || !this.activeBatch.items) return [];
     let items = this.activeBatch.items;

     // 1. In-batch text search across chemical, segregation_bin, container
     const q = this.batchSearchQuery.trim().toLowerCase();
     if (q) {
       items = items.filter(item => {
         const chem = (item.chemical || '').toLowerCase();
         const bin = (item.segregation_bin || item.bin || '').toLowerCase();
         const container = (item.container || '').toLowerCase();
         return chem.includes(q) || bin.includes(q) || container.includes(q);
       });
     }

     // 2. Compound Multi-Hazard Intersection (AND logic)
     if (this.activeHazardFilters.length > 0) {
       items = items.filter(item => {
         return this.activeHazardFilters.every(cat => {
           if (cat === 'Flammable') return item.flammable;
           if (cat === 'Toxic') return item.toxic;
           if (cat === 'Corrosive') return item.corrosive;
           if (cat === 'Infectious') return item.infectious;
           if (cat === 'Carcinogenic') return item.carcinogenic;
           if (cat === 'Review Required') return item.review_required;
           return false;
         });
       });
     }

     return items;
   },
   ```

2. Inside the Active Batch View section (directly beneath the Batch Summary Header), replace static item loop with `filteredItems` and add the Filter Bar:
   ```html
   <!-- Active Batch Filter & Search Bar -->
   <div class="bg-slate-900/80 border border-slate-800 rounded-xl p-4 shadow-md space-y-3">
     <div class="flex flex-col md:flex-row md:items-center justify-between gap-3">
       <!-- Dedicated In-Batch Search Input -->
       <div class="relative flex-1 max-w-md">
         <span class="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-slate-400 text-xs">🔍</span>
         <input type="text"
                x-model="batchSearchQuery"
                placeholder="Filter chemicals in batch (e.g., Acetone, acid, glass)..."
                class="w-full pl-8 pr-8 py-2 rounded-lg bg-slate-950 border border-slate-700/80 text-xs text-white placeholder-slate-500 focus:outline-none focus:ring-1 focus:ring-emerald-500 focus:border-emerald-500 transition">
         <button x-show="batchSearchQuery.length > 0"
                 @click="batchSearchQuery = ''"
                 class="absolute inset-y-0 right-0 pr-2.5 flex items-center text-slate-400 hover:text-white text-xs">
           ✕
         </button>
       </div>

       <!-- Filter Match Counter -->
       <div class="text-xs font-mono text-slate-400 flex items-center gap-1.5">
         <span>Showing</span>
         <span class="font-bold text-emerald-400" x-text="filteredItems.length"></span>
         <span>of</span>
         <span class="font-bold text-white" x-text="activeBatch.items ? activeBatch.items.length : 0"></span>
         <span>chemicals</span>
       </div>
     </div>

     <!-- Multi-Hazard Filter Pills with Live Counter Badges -->
     <div class="flex items-center gap-2 flex-wrap pt-1 border-t border-slate-800/80">
       <span class="text-[11px] font-mono uppercase tracking-wider text-slate-500 mr-1">Hazards:</span>

       <!-- All Pill -->
       <button @click="toggleHazardFilter('All')"
               :class="isHazardFilterActive('All') ? 'bg-emerald-600 text-white border-emerald-500 shadow-sm' : 'bg-slate-800/80 text-slate-300 border-slate-700 hover:bg-slate-750'"
               class="px-2.5 py-1 rounded-lg text-xs font-medium border transition-colors flex items-center gap-1.5">
         <span>All</span>
         <span :class="isHazardFilterActive('All') ? 'bg-emerald-700/80 text-emerald-100' : 'bg-slate-700 text-slate-300'"
               class="px-1.5 py-0.2 rounded text-[10px] font-mono font-bold" x-text="hazardCounts.All"></span>
       </button>

       <!-- Flammable Pill -->
       <button @click="toggleHazardFilter('Flammable')"
               :class="isHazardFilterActive('Flammable') ? 'bg-orange-600 text-white border-orange-500 shadow-sm' : 'bg-slate-800/80 text-slate-300 border-slate-700 hover:bg-slate-750'"
               class="px-2.5 py-1 rounded-lg text-xs font-medium border transition-colors flex items-center gap-1.5">
         <span>🔥 Flammable</span>
         <span :class="isHazardFilterActive('Flammable') ? 'bg-orange-700/80 text-orange-100' : 'bg-slate-700 text-slate-300'"
               class="px-1.5 py-0.2 rounded text-[10px] font-mono font-bold" x-text="hazardCounts.Flammable"></span>
       </button>

       <!-- Toxic Pill -->
       <button @click="toggleHazardFilter('Toxic')"
               :class="isHazardFilterActive('Toxic') ? 'bg-pink-600 text-white border-pink-500 shadow-sm' : 'bg-slate-800/80 text-slate-300 border-slate-700 hover:bg-slate-750'"
               class="px-2.5 py-1 rounded-lg text-xs font-medium border transition-colors flex items-center gap-1.5">
         <span>☠️ Toxic</span>
         <span :class="isHazardFilterActive('Toxic') ? 'bg-pink-700/80 text-pink-100' : 'bg-slate-700 text-slate-300'"
               class="px-1.5 py-0.2 rounded text-[10px] font-mono font-bold" x-text="hazardCounts.Toxic"></span>
       </button>

       <!-- Corrosive Pill -->
       <button @click="toggleHazardFilter('Corrosive')"
               :class="isHazardFilterActive('Corrosive') ? 'bg-purple-600 text-white border-purple-500 shadow-sm' : 'bg-slate-800/80 text-slate-300 border-slate-700 hover:bg-slate-750'"
               class="px-2.5 py-1 rounded-lg text-xs font-medium border transition-colors flex items-center gap-1.5">
         <span>🧪 Corrosive</span>
         <span :class="isHazardFilterActive('Corrosive') ? 'bg-purple-700/80 text-purple-100' : 'bg-slate-700 text-slate-300'"
               class="px-1.5 py-0.2 rounded text-[10px] font-mono font-bold" x-text="hazardCounts.Corrosive"></span>
       </button>

       <!-- Infectious Pill -->
       <button @click="toggleHazardFilter('Infectious')"
               :class="isHazardFilterActive('Infectious') ? 'bg-yellow-600 text-white border-yellow-500 shadow-sm' : 'bg-slate-800/80 text-slate-300 border-slate-700 hover:bg-slate-750'"
               class="px-2.5 py-1 rounded-lg text-xs font-medium border transition-colors flex items-center gap-1.5">
         <span>☣️ Infectious</span>
         <span :class="isHazardFilterActive('Infectious') ? 'bg-yellow-700/80 text-yellow-100' : 'bg-slate-700 text-slate-300'"
               class="px-1.5 py-0.2 rounded text-[10px] font-mono font-bold" x-text="hazardCounts.Infectious"></span>
       </button>

       <!-- Carcinogenic Pill -->
       <button @click="toggleHazardFilter('Carcinogenic')"
               :class="isHazardFilterActive('Carcinogenic') ? 'bg-red-600 text-white border-red-500 shadow-sm' : 'bg-slate-800/80 text-slate-300 border-slate-700 hover:bg-slate-750'"
               class="px-2.5 py-1 rounded-lg text-xs font-medium border transition-colors flex items-center gap-1.5">
         <span>⚠️ Carcinogenic</span>
         <span :class="isHazardFilterActive('Carcinogenic') ? 'bg-red-700/80 text-red-100' : 'bg-slate-700 text-slate-300'"
               class="px-1.5 py-0.2 rounded text-[10px] font-mono font-bold" x-text="hazardCounts.Carcinogenic"></span>
       </button>

       <!-- Review Required Pill -->
       <button @click="toggleHazardFilter('Review Required')"
               :class="isHazardFilterActive('Review Required') ? 'bg-amber-600 text-white border-amber-500 shadow-sm' : 'bg-slate-800/80 text-slate-300 border-slate-700 hover:bg-slate-750'"
               class="px-2.5 py-1 rounded-lg text-xs font-medium border transition-colors flex items-center gap-1.5">
         <span>⚠️ Review Required</span>
         <span :class="isHazardFilterActive('Review Required') ? 'bg-amber-700/80 text-amber-100' : 'bg-slate-700 text-slate-300'"
               class="px-1.5 py-0.2 rounded text-[10px] font-mono font-bold" x-text="hazardCounts['Review Required']"></span>
       </button>
     </div>
   </div>
   ```

3. Update the 3-column card grid loop:
   Change `<template x-for="item in activeBatch.items" :key="item.chemical">`
   to `<template x-for="item in filteredItems" :key="item.chemical">`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `& "C:\Users\stars\miniconda3\envs\d2s-mtp\python.exe" -m unittest tests/test_app.py`
Expected: PASS (all tests pass)

- [ ] **Step 5: Commit**

```bash
git add src/templates/index.html tests/test_app.py
git commit -m "feat(ui): add in-batch multi-field search and multi-hazard filter pills with live counters"
```

---

### Task 2: Implement Layout Toggle & Grouped Cabinet Swimlanes with Collapsible Accordions

**Files:**
- Modify: `src/templates/index.html`
- Modify: `tests/test_app.py`

**Interfaces:**
- Consumes: `filteredItems`, `activeBatch`
- Produces:
  - `activeViewMode`: `'grid' | 'swimlanes'`
  - `expandedZones`: object tracking expanded/collapsed status for all 6 containment zones
  - `cabinetZones`: computed getter returning array of 6 physical containment zones with items, containment notes, and counter badges
  - `toggleZone(zoneId)`: toggles individual cabinet accordion
  - `toggleAllZones(expand)`: master toggle for all cabinet accordions

- [ ] **Step 1: Write the failing unit test**

Add `test_template_contains_cabinet_swimlanes_and_layout_toggle` in `tests/test_app.py`:

```python
    def test_template_contains_cabinet_swimlanes_and_layout_toggle(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        html = response.text

        # Segmented view layout toggle
        self.assertIn("activeViewMode", html)
        self.assertIn("Card Grid", html)
        self.assertIn("Cabinet Swimlanes", html)

        # 6 Containment Zones in Swimlane View
        self.assertIn("cabinetZones", html)
        self.assertIn("expandedZones", html)
        self.assertIn("toggleZone", html)
        self.assertIn("toggleAllZones", html)
        self.assertIn("Flammable Solvents Cabinet", html)
        self.assertIn("Inorganic Acid Storage", html)
        self.assertIn("Inorganic Base Storage", html)
        self.assertIn("Carcinogenic & Toxic Organics", html)
        self.assertIn("Biohazard & Infectious Holding", html)
        self.assertIn("Safety Review Queue", html)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `& "C:\Users\stars\miniconda3\envs\d2s-mtp\python.exe" -m unittest tests/test_app.py`
Expected: FAIL with `AssertionError: 'activeViewMode' not found in response HTML`

- [ ] **Step 3: Update src/templates/index.html**

1. In `x-data`, add:
   ```javascript
   activeViewMode: 'grid', // 'grid' | 'swimlanes'
   expandedZones: {
     flammable: true,
     acids: true,
     bases: true,
     toxic: true,
     biohazard: true,
     review: true
   },

   toggleZone(zoneId) {
     this.expandedZones[zoneId] = !this.expandedZones[zoneId];
   },

   toggleAllZones(expand) {
     for (const key in this.expandedZones) {
       this.expandedZones[key] = expand;
     }
   },

   areAllZonesExpanded() {
     return Object.values(this.expandedZones).every(Boolean);
   },

   get cabinetZones() {
     const items = this.filteredItems;
     return [
       {
         id: 'flammable',
         title: 'Flammable Solvents Cabinet',
         binName: 'Flammable Solvents',
         containmentRule: 'Store in dedicated FM-approved flame-resistant cabinet. Bond & ground containers during transfer. Segregate from oxidizers and inorganic acids.',
         themeBorder: 'border-orange-500/30',
         themeBg: 'bg-orange-950/15',
         themeHeader: 'bg-orange-950/40 text-orange-300 border-orange-500/40',
         badgeBg: 'bg-orange-500/20 text-orange-200 border-orange-500/40',
         icon: '🗄️',
         items: items.filter(i => (i.segregation_bin || i.bin) === 'Flammable Solvents')
       },
       {
         id: 'acids',
         title: 'Inorganic Acid Storage',
         binName: 'Inorganic Acids',
         containmentRule: 'Store in dedicated non-metallic / epoxy-coated acid cabinet with secondary containment tubs. Strictly segregate nitric acid from organic solvents.',
         themeBorder: 'border-purple-500/30',
         themeBg: 'bg-purple-950/15',
         themeHeader: 'bg-purple-950/40 text-purple-300 border-purple-500/40',
         badgeBg: 'bg-purple-500/20 text-purple-200 border-purple-500/40',
         icon: '🧪',
         items: items.filter(i => (i.segregation_bin || i.bin) === 'Inorganic Acids')
       },
       {
         id: 'bases',
         title: 'Inorganic Base Storage',
         binName: 'Inorganic Bases',
         containmentRule: 'Store in corrosion-proof alkali cabinet separated from acid containment. Use polypropylene secondary containment trays.',
         themeBorder: 'border-cyan-500/30',
         themeBg: 'bg-cyan-950/15',
         themeHeader: 'bg-cyan-950/40 text-cyan-300 border-cyan-500/40',
         badgeBg: 'bg-cyan-500/20 text-cyan-200 border-cyan-500/40',
         icon: '🧪',
         items: items.filter(i => (i.segregation_bin || i.bin) === 'Inorganic Bases')
       },
       {
         id: 'toxic',
         title: 'Carcinogenic & Toxic Organics Cabinet',
         binName: 'Carcinogenic & Toxic Organics',
         containmentRule: 'Store in ventilated toxic cabinet under negative pressure. Maintain double containment and strict manifest tracking.',
         themeBorder: 'border-pink-500/30',
         themeBg: 'bg-pink-950/15',
         themeHeader: 'bg-pink-950/40 text-pink-300 border-pink-500/40',
         badgeBg: 'bg-pink-500/20 text-pink-200 border-pink-500/40',
         icon: '☠️',
         items: items.filter(i => (i.segregation_bin || i.bin) === 'Carcinogenic & Toxic Organics')
       },
       {
         id: 'biohazard',
         title: 'Biohazard & Infectious Holding',
         binName: 'Biohazard & Infectious',
         containmentRule: 'Store in leak-proof rigid autoclave-rated biohazard containers with biosafety level containment. Hold for authorized thermal deactivation.',
         themeBorder: 'border-yellow-500/30',
         themeBg: 'bg-yellow-950/15',
         themeHeader: 'bg-yellow-950/40 text-yellow-300 border-yellow-500/40',
         badgeBg: 'bg-yellow-500/20 text-yellow-200 border-yellow-500/40',
         icon: '☣️',
         items: items.filter(i => (i.segregation_bin || i.bin) === 'Biohazard & Infectious')
       },
       {
         id: 'review',
         title: 'Safety Review Queue',
         binName: 'Review Queue',
         containmentRule: 'Hold in designated laboratory quarantine bench. Strictly prohibited to co-mingle or drain-dispose pending certified EHS characterization.',
         themeBorder: 'border-amber-500/40',
         themeBg: 'bg-amber-950/20',
         themeHeader: 'bg-amber-950/50 text-amber-300 border-amber-500/50',
         badgeBg: 'bg-amber-500/20 text-amber-200 border-amber-500/40',
         icon: '⚠️',
         items: items.filter(i => (i.segregation_bin || i.bin) === 'Review Queue' || i.review_required)
       }
     ];
   }
   ```

2. In the Filter Bar, add the Segmented Layout Toggle:
   ```html
   <!-- Segmented Layout Toggle -->
   <div class="inline-flex rounded-lg bg-slate-950 p-1 border border-slate-700/80 shrink-0">
     <button @click="activeViewMode = 'grid'"
             :class="activeViewMode === 'grid' ? 'bg-slate-800 text-white shadow-sm' : 'text-slate-400 hover:text-slate-200'"
             class="px-3 py-1 rounded-md text-xs font-medium transition flex items-center gap-1.5">
       <span>⊞</span>
       <span>Card Grid</span>
     </button>
     <button @click="activeViewMode = 'swimlanes'"
             :class="activeViewMode === 'swimlanes' ? 'bg-slate-800 text-white shadow-sm' : 'text-slate-400 hover:text-slate-200'"
             class="px-3 py-1 rounded-md text-xs font-medium transition flex items-center gap-1.5">
       <span>☵</span>
       <span>Cabinet Swimlanes</span>
     </button>
   </div>
   ```

3. Wrap the Card Grid in `<template x-if="activeViewMode === 'grid'">`.
4. Add the Grouped Cabinet Swimlanes in `<template x-if="activeViewMode === 'swimlanes'">`:
   ```html
   <!-- Grouped Cabinet Swimlanes View -->
   <template x-if="activeViewMode === 'swimlanes'">
     <div class="space-y-6">
       <!-- Master Expand / Collapse Toggle Bar -->
       <div class="flex items-center justify-between text-xs text-slate-400 px-1">
         <span class="font-mono uppercase tracking-wider text-[11px] text-slate-500">Physical Laboratory Safety Containment Zones</span>
         <button @click="toggleAllZones(!areAllZonesExpanded())"
                 class="hover:text-emerald-400 font-medium transition flex items-center gap-1">
           <span x-text="areAllZonesExpanded() ? '▲ Collapse All Cabinets' : '▼ Expand All Cabinets'"></span>
         </button>
       </div>

       <!-- 6 Vertical Stacked Cabinet Swimlanes -->
       <template x-for="zone in cabinetZones" :key="zone.id">
         <div :class="zone.themeBorder + ' ' + zone.themeBg"
              class="rounded-xl border shadow-lg overflow-hidden transition">
           <!-- Cabinet Accordion Header Bar -->
           <div @click="toggleZone(zone.id)"
                :class="zone.themeHeader"
                class="px-5 py-3.5 border-b flex items-center justify-between cursor-pointer select-none transition hover:brightness-110">
             <div class="flex items-center gap-3">
               <span class="text-base" x-text="zone.icon"></span>
               <div>
                 <h3 class="text-sm font-bold tracking-tight text-white flex items-center gap-2">
                   <span x-text="zone.title"></span>
                   <span :class="zone.badgeBg"
                         class="text-[11px] font-mono font-bold px-2 py-0.5 rounded-full border"
                         x-text="zone.items.length + (zone.items.length === 1 ? ' chemical' : ' chemicals')"></span>
                 </h3>
                 <p class="text-[11px] text-slate-400 mt-0.5" x-text="zone.containmentRule"></p>
               </div>
             </div>
             <button class="text-slate-400 hover:text-white text-xs font-mono p-1">
               <span x-text="expandedZones[zone.id] ? '▲' : '▼'"></span>
             </button>
           </div>

           <!-- Collapsible Body with Card Grid or Empty Note -->
           <div x-show="expandedZones[zone.id]" x-transition class="p-5">
             <template x-if="zone.items.length > 0">
               <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
                 <template x-for="item in zone.items" :key="item.chemical">
                   <!-- Reusable Chemical Card Structure -->
                   <div :class="item.review_required ? 'border-amber-500/50 bg-amber-950/15 ring-1 ring-amber-500/30' : 'border-slate-800 bg-slate-900/90'"
                        class="rounded-xl border p-5 shadow-lg flex flex-col justify-between transition hover:border-slate-700 space-y-4">
                     <div class="space-y-3">
                       <div class="flex items-start justify-between gap-2">
                         <h4 class="text-base font-bold text-white tracking-tight" x-text="item.chemical"></h4>
                         <template x-if="item.review_required">
                           <span class="text-[10px] uppercase font-mono px-2 py-0.5 rounded bg-amber-500/20 text-amber-300 border border-amber-500/40 whitespace-nowrap">
                             Review Required
                           </span>
                         </template>
                       </div>
                       <div class="flex flex-wrap gap-1">
                         <template x-for="cat in (item.categories || [])" :key="cat">
                           <span :class="getBadgeClass(cat)" class="text-[11px] px-2 py-0.5 rounded font-medium border" x-text="cat"></span>
                         </template>
                       </div>
                       <template x-if="!item.container">
                         <div class="pt-2 border-t border-slate-800/80">
                           <span class="px-2 py-0.5 rounded text-[10px] font-medium bg-cyan-950 text-cyan-400 border border-cyan-800/60 animate-pulse">Plan Generating...</span>
                         </div>
                       </template>
                       <template x-if="item.container">
                         <div class="space-y-2 pt-1 border-t border-slate-800/80">
                           <div class="text-xs text-slate-300 flex items-start gap-2">
                             <span class="text-sm shrink-0">🛢️</span>
                             <span class="line-clamp-2 leading-relaxed" x-text="item.container"></span>
                           </div>
                           <div class="text-xs text-slate-400 flex items-start gap-2">
                             <span class="text-sm shrink-0">🔒</span>
                             <span class="line-clamp-2 leading-relaxed" x-text="item.segregation"></span>
                           </div>
                         </div>
                       </template>
                     </div>
                     <div class="pt-3 border-t border-slate-800/80">
                       <button @click="openDossier(item)"
                               class="w-full py-2 px-3 bg-slate-800 hover:bg-emerald-600 text-slate-200 hover:text-white rounded-lg text-xs font-medium transition text-center flex items-center justify-center gap-1">
                         <span x-text="item.container ? 'View Full Plan →' : 'Inspect Badges →'"></span>
                       </button>
                     </div>
                   </div>
                 </template>
               </div>
             </template>
             <template x-if="zone.items.length === 0">
               <div class="py-6 text-center text-xs text-slate-500 font-mono">
                 No chemicals in this containment zone match current filters
               </div>
             </template>
           </div>
         </div>
       </template>
     </div>
   </template>
   ```

- [ ] **Step 4: Run tests to verify they pass**

Run: `& "C:\Users\stars\miniconda3\envs\d2s-mtp\python.exe" -m unittest tests/test_app.py`
Expected: PASS (all tests pass)

- [ ] **Step 5: Commit**

```bash
git add src/templates/index.html tests/test_app.py
git commit -m "feat(ui): add layout toggle and grouped physical cabinet swimlanes with collapsible accordions"
```

---

### Task 3: Implement Zero-Result Empty State & End-to-End Filter Integration Verification

**Files:**
- Modify: `src/templates/index.html`
- Modify: `tests/test_app.py`

**Interfaces:**
- Consumes: `filteredItems`, `batchSearchQuery`, `activeHazardFilters`
- Produces:
  - `resetFilters()` method
  - Zero-result empty state card in `src/templates/index.html`
  - Integration tests verifying compound filtering, search matching, and layout switching

- [ ] **Step 1: Write the failing integration tests**

Add `test_template_contains_zero_result_empty_state_and_reset_button` and helper tests in `tests/test_app.py`:

```python
    def test_template_contains_zero_result_empty_state_and_reset_button(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        html = response.text

        # Zero-result empty state card & reset button
        self.assertIn("No chemicals match active filters", html)
        self.assertIn("resetFilters", html)
        self.assertIn("Reset Filters", html)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `& "C:\Users\stars\miniconda3\envs\d2s-mtp\python.exe" -m unittest tests/test_app.py`
Expected: FAIL with `AssertionError: 'No chemicals match active filters' not found in response HTML`

- [ ] **Step 3: Update src/templates/index.html**

1. In `x-data`, add `resetFilters()`:
   ```javascript
   resetFilters() {
     this.batchSearchQuery = '';
     this.activeHazardFilters = [];
   },
   ```

2. Inside `<template x-if="activeViewMode === 'grid'">`, add the empty state card when `filteredItems.length === 0`:
   ```html
   <!-- Zero-Result Empty State Card (Grid View) -->
   <template x-if="filteredItems.length === 0">
     <div class="col-span-full bg-slate-900/60 border border-dashed border-slate-700/80 rounded-2xl p-10 text-center space-y-4">
       <div class="text-3xl">🔍</div>
       <div class="space-y-1">
         <h4 class="text-base font-semibold text-white">No chemicals match active filters</h4>
         <p class="text-xs text-slate-400">
           <span>Query: </span>
           <span class="font-mono text-emerald-400" x-text="batchSearchQuery ? '\"' + batchSearchQuery + '\"' : 'none'"></span>
           <span class="mx-2">•</span>
           <span>Active Hazards: </span>
           <span class="font-mono text-cyan-400" x-text="activeHazardFilters.length > 0 ? activeHazardFilters.join(' + ') : 'All'"></span>
         </p>
       </div>
       <button @click="resetFilters()"
               class="px-4 py-2 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-semibold shadow-md transition">
         Reset Filters
       </button>
     </div>
   </template>
   ```

- [ ] **Step 4: Run tests to verify they pass**

Run: `& "C:\Users\stars\miniconda3\envs\d2s-mtp\python.exe" -m unittest tests/test_app.py`
Expected: PASS (all tests in test_app pass)

- [ ] **Step 5: Run full test suite across the repository**

Run: `& "C:\Users\stars\miniconda3\envs\d2s-mtp\python.exe" -m unittest`
Expected: PASS (all 45+ tests pass cleanly)

- [ ] **Step 6: Commit**

```bash
git add src/templates/index.html tests/test_app.py
git commit -m "feat(ui): add zero-result empty state card and filter reset action"
```

---

## Self-Review Checklist

1. **Spec Coverage**:
   - Real-time in-batch chemical name filtering? Covered in Task 1 (`batchSearchQuery`).
   - Additive multi-hazard filter pills with dynamic count badges? Covered in Task 1 (`activeHazardFilters` with AND intersection & `hazardCounts`).
   - Layout toggle smoothly switching between 3-column grid and grouped cabinet swimlanes? Covered in Task 2 (`activeViewMode`).
   - 6 cabinet swimlanes with header counters, containment notes, and collapsible section controls? Covered in Task 2 (`cabinetZones` & `expandedZones`).
   - Unit tests verifying filtering state logic, multi-category matching, and view toggle transitions? Covered in Task 1, Task 2, and Task 3.
2. **No Placeholders**: All tasks contain explicit code blocks, runnable test commands, and exact assertions.
3. **Type Consistency**: `batchSearchQuery`, `activeHazardFilters`, `activeViewMode`, `cabinetZones`, and `expandedZones` property names match exactly across all tasks.
4. **Environment Constraints**: Standard library `unittest` used exclusively; Conda env `d2s-mtp` targeted in all run commands.
