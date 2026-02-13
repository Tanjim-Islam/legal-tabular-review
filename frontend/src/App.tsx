import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import "./App.css";

type ReviewState = "CONFIRMED" | "REJECTED" | "MANUAL_UPDATED" | "MISSING_DATA";

type Citation = {
  document_id: string;
  document_identifier: string;
  location_type: string;
  location: string;
  snippet: string;
  char_start: number;
  char_end: number;
  coordinates: null;
} | null;

type Cell = {
  cell_id: string | null;
  document_id: string;
  document_identifier: string;
  value: string | null;
  value_raw: string | null;
  value_normalized: string | null;
  review_state: ReviewState;
  confidence: number;
  confidence_reasons: string[];
  citation: Citation;
};

type TableRow = {
  field_key: string;
  field_label: string;
  field_type: string;
  cells: Cell[];
};

type TablePayload = {
  job: {
    id: string;
    mode: "quick" | "full";
    status: string;
    created_at: string;
    finished_at: string | null;
  } | null;
  documents: { id: string; identifier: string }[];
  fields: { key: string; label: string; type: string }[];
  rows: TableRow[];
};

const API_BASE = import.meta.env.VITE_API_BASE || "http://127.0.0.1:8000";

async function fetchJson<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: {
      "Content-Type": "application/json",
      ...(options?.headers || {}),
    },
    ...options,
  });
  if (!response.ok) {
    throw new Error(`Request failed: ${response.status}`);
  }
  return (await response.json()) as T;
}

export default function App() {
  const [table, setTable] = useState<TablePayload | null>(null);
  const [selectedCell, setSelectedCell] = useState<Cell | null>(null);
  const [manualValue, setManualValue] = useState("");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("Ready");

  async function loadTable(jobId?: string) {
    const query = jobId ? `?job_id=${encodeURIComponent(jobId)}` : "";
    const payload = await fetchJson<TablePayload>(`/results/table${query}`);
    setTable(payload);
    if (selectedCell?.cell_id) {
      const refreshedCell = payload.rows
        .flatMap((row) => row.cells)
        .find((cell) => cell.cell_id === selectedCell.cell_id);
      setSelectedCell(refreshedCell || null);
    }
  }

  async function runExtraction(mode: "quick" | "full") {
    try {
      setBusy(true);
      setMessage(`Running ${mode} extraction...`);
      const result = await fetchJson<{ job: { id: string; status: string } }>(
        "/runs",
        {
          method: "POST",
          body: JSON.stringify({ mode, wait: true }),
        },
      );
      await loadTable(result.job.id);
      setMessage(`Run ${result.job.id.slice(0, 8)} completed (${mode}).`);
    } catch (error) {
      setMessage(`Run failed: ${(error as Error).message}`);
    } finally {
      setBusy(false);
    }
  }

  async function updateCell(payload: {
    review_state?: ReviewState;
    manual_value?: string;
    reason?: string;
  }) {
    if (!selectedCell?.cell_id) {
      return;
    }
    try {
      setBusy(true);
      await fetchJson(`/cells/${selectedCell.cell_id}`, {
        method: "PATCH",
        body: JSON.stringify({ actor: "ui-reviewer", ...payload }),
      });
      await loadTable(table?.job?.id);
      setMessage("Cell updated.");
    } catch (error) {
      setMessage(`Update failed: ${(error as Error).message}`);
    } finally {
      setBusy(false);
    }
  }

  async function exportFile(kind: "csv" | "xlsx") {
    if (!table?.job?.id) {
      setMessage("Run extraction first.");
      return;
    }
    try {
      setBusy(true);
      const response = await fetch(`${API_BASE}/exports/${kind}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ job_id: table.job.id }),
      });
      if (!response.ok) {
        throw new Error(`Export failed: ${response.status}`);
      }
      const blob = await response.blob();
      const contentDisposition =
        response.headers.get("content-disposition") || "";
      const filenameMatch = contentDisposition.match(
        /filename=\"?([^\";]+)\"?/i,
      );
      const filename = filenameMatch?.[1] || `review-export.${kind}`;
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = filename;
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      URL.revokeObjectURL(url);
      setMessage(`Exported ${filename}`);
    } catch (error) {
      setMessage((error as Error).message);
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => {
    loadTable().catch((error) =>
      setMessage(`Failed to load table: ${(error as Error).message}`),
    );
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const hasRows = (table?.rows.length || 0) > 0;
  const selectedCitation = selectedCell?.citation;
  const documents = useMemo(() => table?.documents || [], [table]);

  const tableWrapRef = useRef<HTMLElement>(null);

  useEffect(() => {
    const el = tableWrapRef.current;
    if (!el) return;
    const onWheel = (e: WheelEvent) => {
      const hasHorizontalOverflow = el.scrollWidth > el.clientWidth;
      if (!hasHorizontalOverflow) return;
      // Only hijack vertical scroll (deltaY) and convert to horizontal
      if (Math.abs(e.deltaY) > Math.abs(e.deltaX)) {
        const atLeft = el.scrollLeft <= 0;
        const atRight = el.scrollLeft + el.clientWidth >= el.scrollWidth - 1;
        // Allow page scroll if already at the edge in the scroll direction
        if ((e.deltaY < 0 && atLeft) || (e.deltaY > 0 && atRight)) return;
        e.preventDefault();
        el.scrollLeft += e.deltaY;
      }
    };
    el.addEventListener("wheel", onWheel, { passive: false });
    return () => el.removeEventListener("wheel", onWheel);
  }, [hasRows]);

  return (
    <main className="page">
      <header className="header">
        <div>
          <h1>Legal Tabular Review</h1>
          <p>
            Deterministic extraction with citations, confidence, and review
            actions.
          </p>
        </div>
        <div className="controls">
          <button disabled={busy} onClick={() => runExtraction("quick")}>
            Run Quick
          </button>
          <button disabled={busy} onClick={() => runExtraction("full")}>
            Run Full
          </button>
          <button
            disabled={busy || !table?.job?.id}
            onClick={() => exportFile("csv")}
          >
            Export CSV
          </button>
          <button
            disabled={busy || !table?.job?.id}
            onClick={() => exportFile("xlsx")}
          >
            Export XLSX
          </button>
        </div>
      </header>

      <section className="status">
        <span>{message}</span>
        {table?.job ? (
          <span>
            Job: {table.job.id.slice(0, 8)} ({table.job.mode},{" "}
            {table.job.status})
          </span>
        ) : null}
      </section>

      <section className="table-wrap" ref={tableWrapRef}>
        {!hasRows ? (
          <p>No extracted rows yet. Run quick mode first.</p>
        ) : (
          <table>
            <thead>
              <tr>
                <th>Field</th>
                {documents.map((document) => (
                  <th key={document.id}>{document.identifier}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {table?.rows.map((row) => (
                <tr key={row.field_key}>
                  <th>{row.field_label}</th>
                  {row.cells.map((cell) => (
                    <td
                      key={`${row.field_key}-${cell.document_id}`}
                      className={
                        selectedCell?.cell_id === cell.cell_id ? "selected" : ""
                      }
                      onClick={() => {
                        setSelectedCell(cell);
                        setManualValue(cell.value || "");
                      }}
                    >
                      <div className="cell-value">
                        {cell.value || "(missing)"}
                      </div>
                      <div className="cell-meta">
                        <span
                          className={`tag ${cell.review_state.toLowerCase()}`}
                        >
                          {cell.review_state}
                        </span>
                        <span>{cell.confidence.toFixed(2)}</span>
                      </div>
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>

      <aside className="detail">
        <h2>Cell Detail</h2>
        {!selectedCell ? (
          <p>
            Select a cell to inspect citation, confidence, and review actions.
          </p>
        ) : (
          <div className="detail-body">
            <p>
              <strong>Document:</strong> {selectedCell.document_identifier}
            </p>
            <p>
              <strong>Current Value:</strong>{" "}
              {selectedCell.value || "(missing)"}
            </p>
            <p>
              <strong>Review State:</strong> {selectedCell.review_state}
            </p>
            <p>
              <strong>Confidence:</strong> {selectedCell.confidence.toFixed(2)}{" "}
              ({selectedCell.confidence_reasons.join(", ")})
            </p>
            <p>
              <strong>Citation Location:</strong>{" "}
              {selectedCitation
                ? `${selectedCitation.location_type} ${selectedCitation.location}`
                : "N/A"}
            </p>
            <p className="snippet">
              <strong>Snippet:</strong> {selectedCitation?.snippet || "N/A"}
            </p>

            <div className="detail-controls">
              <button
                disabled={busy}
                onClick={() => updateCell({ review_state: "CONFIRMED" })}
              >
                Confirm
              </button>
              <button
                disabled={busy}
                onClick={() => updateCell({ review_state: "REJECTED" })}
              >
                Reject
              </button>
            </div>

            <label>
              Manual Value
              <input
                value={manualValue}
                onChange={(event) => setManualValue(event.target.value)}
                placeholder="Override value"
              />
            </label>
            <button
              disabled={busy || !manualValue.trim()}
              onClick={() =>
                updateCell({
                  manual_value: manualValue.trim(),
                  reason: "manual edit",
                })
              }
            >
              Save Manual Edit
            </button>
          </div>
        )}
      </aside>
    </main>
  );
}
