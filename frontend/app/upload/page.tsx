"use client";

import { useRef, useState } from "react";
import { ApiError, processUpload, uploadCsv } from "@/lib/api";
import { ENTITY_LABELS, ENTITY_STANDARD_FIELDS } from "@/lib/entityFields";
import type { EntityType, ProcessResult, UploadResponse } from "@/lib/types";

const ENTITY_TYPES = Object.keys(ENTITY_LABELS) as EntityType[];
const NO_MAP = "__none__";

export default function UploadPage() {
  const [entityType, setEntityType] = useState<EntityType>("invoices");
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [upload, setUpload] = useState<UploadResponse | null>(null);
  const [mapping, setMapping] = useState<Record<string, string>>({});
  const [processing, setProcessing] = useState(false);
  const [result, setResult] = useState<ProcessResult | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  async function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploading(true);
    setError(null);
    setResult(null);
    try {
      const res = await uploadCsv(file, entityType);
      setUpload(res);
      const initialMapping: Record<string, string> = {};
      for (const [col, sugg] of Object.entries(res.suggested_mapping)) {
        if (sugg.standard_field) initialMapping[col] = sugg.standard_field;
      }
      setMapping(initialMapping);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : String(err));
      setUpload(null);
    } finally {
      setUploading(false);
      if (fileRef.current) fileRef.current.value = "";
    }
  }

  async function handleProcess() {
    if (!upload) return;
    setProcessing(true);
    setError(null);
    try {
      const filtered = Object.fromEntries(Object.entries(mapping).filter(([, v]) => v && v !== NO_MAP));
      const res = await processUpload(upload.upload_id, filtered);
      setResult(res);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : String(err));
    } finally {
      setProcessing(false);
    }
  }

  const mappedStandardFields = new Set(Object.values(mapping).filter((v) => v && v !== NO_MAP));
  const requiredMissing = upload
    ? ENTITY_STANDARD_FIELDS[upload.entity_type]
        .filter((f) => !mappedStandardFields.has(f))
        .filter((f) => upload.validation.missing_required_after_mapping.includes(f))
    : [];

  return (
    <div className="flex flex-col gap-6 max-w-4xl">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Upload & Schema Mapping</h1>
        <p className="mt-1 text-sm" style={{ color: "var(--text-secondary)" }}>
          Upload a raw CSV export. Operon auto-suggests how your columns map to Operon&apos;s standard
          schema — review and adjust before processing.
        </p>
      </div>

      <div className="card p-4 flex flex-col gap-4">
        <div className="flex items-end gap-4 flex-wrap">
          <label className="flex flex-col gap-1 text-sm">
            <span style={{ color: "var(--text-secondary)" }}>Data type</span>
            <select
              className="border rounded-md px-3 py-2 bg-transparent"
              style={{ borderColor: "var(--border)" }}
              value={entityType}
              onChange={(e) => setEntityType(e.target.value as EntityType)}
            >
              {ENTITY_TYPES.map((et) => (
                <option key={et} value={et}>
                  {ENTITY_LABELS[et]}
                </option>
              ))}
            </select>
          </label>
          <label className="flex flex-col gap-1 text-sm">
            <span style={{ color: "var(--text-secondary)" }}>CSV file</span>
            <input
              ref={fileRef}
              type="file"
              accept=".csv"
              onChange={handleFileChange}
              disabled={uploading}
              className="text-sm"
            />
          </label>
          {uploading && <span style={{ color: "var(--text-muted)" }}>Uploading & analyzing…</span>}
        </div>
        {error && (
          <div className="text-sm p-3 rounded-md" style={{ color: "var(--status-critical)", background: "rgba(208,59,59,0.08)" }}>
            {error}
          </div>
        )}
      </div>

      {upload && (
        <div className="card p-4 flex flex-col gap-4">
          <div className="flex items-center justify-between flex-wrap gap-2">
            <h2 className="font-medium">
              {upload.filename} — {upload.row_count.toLocaleString()} rows, {upload.column_count} columns
            </h2>
          </div>

          {upload.validation.warnings.length > 0 && (
            <ul className="text-xs list-disc pl-4" style={{ color: "var(--status-warning)" }}>
              {upload.validation.warnings.map((w, i) => (
                <li key={i}>{w}</li>
              ))}
            </ul>
          )}

          <div>
            <h3 className="text-sm font-medium mb-2">Column mapping</h3>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left" style={{ color: "var(--text-muted)" }}>
                    <th className="pb-2 pr-4">Your column</th>
                    <th className="pb-2 pr-4">Maps to</th>
                    <th className="pb-2">Confidence</th>
                  </tr>
                </thead>
                <tbody>
                  {upload.columns.map((col) => {
                    const sugg = upload.suggested_mapping[col];
                    return (
                      <tr key={col} className="border-t" style={{ borderColor: "var(--gridline)" }}>
                        <td className="py-1.5 pr-4 font-mono text-xs">{col}</td>
                        <td className="py-1.5 pr-4">
                          <select
                            className="border rounded px-2 py-1 bg-transparent text-sm"
                            style={{ borderColor: "var(--border)" }}
                            value={mapping[col] ?? NO_MAP}
                            onChange={(e) =>
                              setMapping((m) => ({ ...m, [col]: e.target.value }))
                            }
                          >
                            <option value={NO_MAP}>— ignore —</option>
                            {ENTITY_STANDARD_FIELDS[upload.entity_type].map((f) => (
                              <option key={f} value={f}>
                                {f}
                              </option>
                            ))}
                          </select>
                        </td>
                        <td className="py-1.5 tabular" style={{ color: "var(--text-muted)" }}>
                          {sugg?.standard_field ? `${Math.round(sugg.confidence * 100)}%` : "—"}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>

          {requiredMissing.length > 0 && (
            <div className="text-sm p-3 rounded-md" style={{ color: "var(--status-critical)", background: "rgba(208,59,59,0.08)" }}>
              Missing required field mapping(s): {requiredMissing.join(", ")}. Rows without these will be
              rejected.
            </div>
          )}

          <div>
            <h3 className="text-sm font-medium mb-2">Preview (first {upload.preview_rows.length} rows)</h3>
            <div className="overflow-x-auto max-h-64 overflow-y-auto border rounded-md" style={{ borderColor: "var(--gridline)" }}>
              <table className="w-full text-xs">
                <thead className="sticky top-0" style={{ background: "var(--surface)" }}>
                  <tr>
                    {upload.columns.map((c) => (
                      <th key={c} className="text-left px-2 py-1.5 font-mono whitespace-nowrap">
                        {c}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {upload.preview_rows.map((row, i) => (
                    <tr key={i} className="border-t" style={{ borderColor: "var(--gridline)" }}>
                      {upload.columns.map((c) => (
                        <td key={c} className="px-2 py-1 whitespace-nowrap">
                          {row[c] === null || row[c] === undefined ? "" : String(row[c])}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          <button
            onClick={handleProcess}
            disabled={processing}
            className="self-start px-4 py-2 rounded-md text-sm font-medium text-white disabled:opacity-50"
            style={{ background: "var(--series-ar)" }}
          >
            {processing ? "Processing…" : "Normalize & load into Operon"}
          </button>
        </div>
      )}

      {result && (
        <div className="card p-4">
          <h3 className="font-medium mb-2">Processing result</h3>
          <dl className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-sm">
            <div>
              <dt style={{ color: "var(--text-muted)" }}>Rows in file</dt>
              <dd className="tabular font-medium">{result.rows_in.toLocaleString()}</dd>
            </div>
            <div>
              <dt style={{ color: "var(--text-muted)" }}>Inserted / updated</dt>
              <dd className="tabular font-medium" style={{ color: "var(--status-good)" }}>
                {result.rows_inserted.toLocaleString()}
              </dd>
            </div>
            <div>
              <dt style={{ color: "var(--text-muted)" }}>Rejected</dt>
              <dd className="tabular font-medium" style={{ color: result.rows_rejected ? "var(--status-critical)" : undefined }}>
                {result.rows_rejected.toLocaleString()}
              </dd>
            </div>
            <div>
              <dt style={{ color: "var(--text-muted)" }}>Duplicates removed</dt>
              <dd className="tabular font-medium">{result.rows_deduplicated.toLocaleString()}</dd>
            </div>
          </dl>
          {result.errors.length > 0 && (
            <ul className="text-xs mt-3 list-disc pl-4" style={{ color: "var(--status-warning)" }}>
              {result.errors.map((e, i) => (
                <li key={i}>{e}</li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}
