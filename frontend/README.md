Frontend

React UI for Legal Tabular Review.

Implemented UI features:
- Quick/full extraction run controls
- Side-by-side comparison table (fields x documents)
- Per-cell detail panel with citation + confidence reasons
- Review actions: confirm, reject, manual edit
- CSV/XLSX export buttons

Run:
```bash
npm install
npm run dev
```

Build:
```bash
npm run build
```

Optional API override:
- `VITE_API_BASE` (default: `http://127.0.0.1:8000`)
