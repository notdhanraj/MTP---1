# 06: Institutional Multi-Sheet Excel Export & Run History Archive

**What to build:**
Ensure complete parity with institutional EHS reporting standards and prevent redundant API token spending. Every completed batch run is automatically saved to a local timestamped directory (`data/runs/<timestamp>/`) containing the input spreadsheet, intermediate classification matrix, and finalized management plan workbook. A collapsible run history sidebar displays past batches, allowing users to reload previous inventory analyses in one click. An "Export Excel (.xlsx)" button triggers the download of the official institutional 3-sheet workbook (`Management Plan`, `Classification`, and `Review Required`) matching `hazardous_waste_management_plan.xlsx`. A secondary quick-export button allows downloading the currently filtered card view as a `.csv` file.

**Blocked by:** 03 (Live SSE Batch Processing & Progress Stepper)

**Status:** closed

## Acceptance Criteria

- [x] Completed batch runs are persisted to disk under timestamped run folders with input and output workbooks and metadata.
- [x] A collapsible sidebar lists past runs by date and item count, allowing users to switch active views without re-running LLM APIs.
- [x] Clicking "Export Excel (.xlsx)" generates and downloads a valid 3-sheet workbook containing the `Management Plan` (with all 14 fields), `Classification` matrix, and `Review Required` sheets.
- [x] Clicking "Export Filtered CSV" exports the currently visible items to a lightweight `.csv` format.
- [x] Unit tests verify Excel file generation, asserting sheet names, column headers, and row data parity against existing openpyxl outputs.
