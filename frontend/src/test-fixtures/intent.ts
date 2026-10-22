/* SPDX-License-Identifier: AGPL-3.0-only */
/** Actual API specimens; independent expectations are asserted by tests.
 * Author: Imitiyaz and AI Agent
 */
import type { Answer } from "../api";
const productsSpecimen = {
  workspace_revision: 0,
  resolved_question:
    "What is the total quantity of the individual products and overall products in the file ?",
  clarification_options: [],
  status: "answered",
  execution_path: "structured",
  records: [
    {
      number: 1,
      source_file: "operations.pdf",
      sheet_or_page: "page_1",
      row_or_location: "table_1_row_1",
      values: {
        Product: "BOLT-A",
        Unit: "pcs",
        Quantity: "10",
      },
      cell_references: {},
      merged_fields: [],
      cell_formats: {},
      formula_fields: {},
      continuation_fields: {},
    },
    {
      number: 2,
      source_file: "operations.pdf",
      sheet_or_page: "page_1",
      row_or_location: "table_1_row_2",
      values: {
        Product: "NUT-B",
        Unit: "pcs",
        Quantity: "6",
      },
      cell_references: {},
      merged_fields: [],
      cell_formats: {},
      formula_fields: {},
      continuation_fields: {},
    },
    {
      number: 3,
      source_file: "operations.pdf",
      sheet_or_page: "page_3",
      row_or_location: "table_1_row_1",
      values: {
        Product: "BOLT-A",
        Unit: "pcs",
        Quantity: "4",
      },
      cell_references: {},
      merged_fields: [],
      cell_formats: {},
      formula_fields: {},
      continuation_fields: {},
    },
    {
      number: 4,
      source_file: "operations.pdf",
      sheet_or_page: "page_3",
      row_or_location: "table_1_row_2",
      values: {
        Product: "NUT-B",
        Unit: "pcs",
        Quantity: "8",
      },
      cell_references: {},
      merged_fields: [],
      cell_formats: {},
      formula_fields: {},
      continuation_fields: {},
    },
  ],
  coverage: {
    method: "all_indexed_rows_grouped",
    record_scope: "auto",
    scope_records: 4,
    matched_records: 4,
    returned_records: 4,
    fields: ["Quantity"],
    missing_cells: [],
    complete: true,
    calculation_complete: true,
    calculation_included_records: 4,
    calculation_excluded_cells: 0,
    grouped_results: 3,
    group_field: "Product",
    population_basis: "all_selected_records",
    resolved_scopes: [],
    page: 1,
    total_pages: 1,
    page_size: 50,
    calculation_uses_all_matches: false,
  },
  calculation: null,
  grouped_results: [
    {
      label: "Overall",
      scope: "Whole file",
      entities: [],
      status: "answered",
      answer:
        "Whole file \u00b7 Overall: Total Quantity: 28 pcs. [1] [2] [3] (+1 source records in evidence)\nWhole file \u00b7 Overall: Based on all 4 matching source records. The calculation evidence contains every operand.\nWhole file \u00b7 Overall: Counting every selected physical source record, as confirmed; repeated values on different sheets remain separate records.\nWhole file \u00b7 Overall \u00b7 BOLT-A \u2014 Quantity: 14 pcs. [1] [3]\nWhole file \u00b7 Overall \u00b7 NUT-B \u2014 Quantity: 14 pcs. [2] [4]",
      record_numbers: [1, 2, 3, 4],
      missing_entities: [],
      calculation: {
        operation: "sum",
        fields: ["Quantity"],
        unit: "pcs",
        rounding: "Exact decimal operands; no rounding",
        result: {
          Quantity: "28",
        },
        operands: [
          {
            number: 1,
            values: {
              Quantity: "10",
            },
            source: {
              source_file: "operations.pdf",
              sheet_or_page: "page_1",
              row_or_location: "table_1_row_1",
            },
            cell_references: {},
          },
          {
            number: 2,
            values: {
              Quantity: "6",
            },
            source: {
              source_file: "operations.pdf",
              sheet_or_page: "page_1",
              row_or_location: "table_1_row_2",
            },
            cell_references: {},
          },
          {
            number: 3,
            values: {
              Quantity: "4",
            },
            source: {
              source_file: "operations.pdf",
              sheet_or_page: "page_3",
              row_or_location: "table_1_row_1",
            },
            cell_references: {},
          },
          {
            number: 4,
            values: {
              Quantity: "8",
            },
            source: {
              source_file: "operations.pdf",
              sheet_or_page: "page_3",
              row_or_location: "table_1_row_2",
            },
            cell_references: {},
          },
        ],
        partial: false,
        excluded_cells: [],
        matched_records: 4,
        included_records: 4,
        population_basis: "all_selected_records",
      },
      contributions: [
        {
          entity: "BOLT-A",
          status: "answered",
          record_numbers: [1, 3],
          calculation: {
            operation: "sum",
            fields: ["Quantity"],
            unit: "pcs",
            rounding: "Exact decimal operands; no rounding",
            result: {
              Quantity: "14",
            },
            operands: [
              {
                number: 1,
                values: {
                  Quantity: "10",
                },
                source: {
                  source_file: "operations.pdf",
                  sheet_or_page: "page_1",
                  row_or_location: "table_1_row_1",
                },
                cell_references: {},
              },
              {
                number: 3,
                values: {
                  Quantity: "4",
                },
                source: {
                  source_file: "operations.pdf",
                  sheet_or_page: "page_3",
                  row_or_location: "table_1_row_1",
                },
                cell_references: {},
              },
            ],
            partial: false,
            excluded_cells: [],
            matched_records: 2,
            included_records: 2,
            population_basis: "all_selected_records",
          },
          missing_cells: [],
        },
        {
          entity: "NUT-B",
          status: "answered",
          record_numbers: [2, 4],
          calculation: {
            operation: "sum",
            fields: ["Quantity"],
            unit: "pcs",
            rounding: "Exact decimal operands; no rounding",
            result: {
              Quantity: "14",
            },
            operands: [
              {
                number: 2,
                values: {
                  Quantity: "6",
                },
                source: {
                  source_file: "operations.pdf",
                  sheet_or_page: "page_1",
                  row_or_location: "table_1_row_2",
                },
                cell_references: {},
              },
              {
                number: 4,
                values: {
                  Quantity: "8",
                },
                source: {
                  source_file: "operations.pdf",
                  sheet_or_page: "page_3",
                  row_or_location: "table_1_row_2",
                },
                cell_references: {},
              },
            ],
            partial: false,
            excluded_cells: [],
            matched_records: 2,
            included_records: 2,
            population_basis: "all_selected_records",
          },
          missing_cells: [],
        },
      ],
    },
    {
      label: "BOLT-A",
      scope: "Whole file",
      entities: ["BOLT-A"],
      status: "answered",
      answer:
        "Whole file \u00b7 BOLT-A: Total Quantity: 14 pcs. [1] [3]\nWhole file \u00b7 BOLT-A: Based on all 2 matching source records. The calculation evidence contains every operand.\nWhole file \u00b7 BOLT-A: Counting every selected physical source record, as confirmed; repeated values on different sheets remain separate records.\nWhole file \u00b7 BOLT-A \u00b7 BOLT-A \u2014 Quantity: 14 pcs. [1] [3]",
      record_numbers: [1, 3],
      missing_entities: [],
      calculation: {
        operation: "sum",
        fields: ["Quantity"],
        unit: "pcs",
        rounding: "Exact decimal operands; no rounding",
        result: {
          Quantity: "14",
        },
        operands: [
          {
            number: 1,
            values: {
              Quantity: "10",
            },
            source: {
              source_file: "operations.pdf",
              sheet_or_page: "page_1",
              row_or_location: "table_1_row_1",
            },
            cell_references: {},
          },
          {
            number: 3,
            values: {
              Quantity: "4",
            },
            source: {
              source_file: "operations.pdf",
              sheet_or_page: "page_3",
              row_or_location: "table_1_row_1",
            },
            cell_references: {},
          },
        ],
        partial: false,
        excluded_cells: [],
        matched_records: 2,
        included_records: 2,
        population_basis: "all_selected_records",
      },
      contributions: [
        {
          entity: "BOLT-A",
          status: "answered",
          record_numbers: [1, 3],
          calculation: {
            operation: "sum",
            fields: ["Quantity"],
            unit: "pcs",
            rounding: "Exact decimal operands; no rounding",
            result: {
              Quantity: "14",
            },
            operands: [
              {
                number: 1,
                values: {
                  Quantity: "10",
                },
                source: {
                  source_file: "operations.pdf",
                  sheet_or_page: "page_1",
                  row_or_location: "table_1_row_1",
                },
                cell_references: {},
              },
              {
                number: 3,
                values: {
                  Quantity: "4",
                },
                source: {
                  source_file: "operations.pdf",
                  sheet_or_page: "page_3",
                  row_or_location: "table_1_row_1",
                },
                cell_references: {},
              },
            ],
            partial: false,
            excluded_cells: [],
            matched_records: 2,
            included_records: 2,
            population_basis: "all_selected_records",
          },
          missing_cells: [],
        },
      ],
    },
    {
      label: "NUT-B",
      scope: "Whole file",
      entities: ["NUT-B"],
      status: "answered",
      answer:
        "Whole file \u00b7 NUT-B: Total Quantity: 14 pcs. [2] [4]\nWhole file \u00b7 NUT-B: Based on all 2 matching source records. The calculation evidence contains every operand.\nWhole file \u00b7 NUT-B: Counting every selected physical source record, as confirmed; repeated values on different sheets remain separate records.\nWhole file \u00b7 NUT-B \u00b7 NUT-B \u2014 Quantity: 14 pcs. [2] [4]",
      record_numbers: [2, 4],
      missing_entities: [],
      calculation: {
        operation: "sum",
        fields: ["Quantity"],
        unit: "pcs",
        rounding: "Exact decimal operands; no rounding",
        result: {
          Quantity: "14",
        },
        operands: [
          {
            number: 2,
            values: {
              Quantity: "6",
            },
            source: {
              source_file: "operations.pdf",
              sheet_or_page: "page_1",
              row_or_location: "table_1_row_2",
            },
            cell_references: {},
          },
          {
            number: 4,
            values: {
              Quantity: "8",
            },
            source: {
              source_file: "operations.pdf",
              sheet_or_page: "page_3",
              row_or_location: "table_1_row_2",
            },
            cell_references: {},
          },
        ],
        partial: false,
        excluded_cells: [],
        matched_records: 2,
        included_records: 2,
        population_basis: "all_selected_records",
      },
      contributions: [
        {
          entity: "NUT-B",
          status: "answered",
          record_numbers: [2, 4],
          calculation: {
            operation: "sum",
            fields: ["Quantity"],
            unit: "pcs",
            rounding: "Exact decimal operands; no rounding",
            result: {
              Quantity: "14",
            },
            operands: [
              {
                number: 2,
                values: {
                  Quantity: "6",
                },
                source: {
                  source_file: "operations.pdf",
                  sheet_or_page: "page_1",
                  row_or_location: "table_1_row_2",
                },
                cell_references: {},
              },
              {
                number: 4,
                values: {
                  Quantity: "8",
                },
                source: {
                  source_file: "operations.pdf",
                  sheet_or_page: "page_3",
                  row_or_location: "table_1_row_2",
                },
                cell_references: {},
              },
            ],
            partial: false,
            excluded_cells: [],
            matched_records: 2,
            included_records: 2,
            population_basis: "all_selected_records",
          },
          missing_cells: [],
        },
      ],
    },
  ],
  warnings: [],
  timings_seconds: {},
  answer:
    "Whole file \u00b7 Overall: Total Quantity: 28 pcs. [1] [2] [3] (+1 source records in evidence)\nWhole file \u00b7 Overall: Based on all 4 matching source records. The calculation evidence contains every operand.\nWhole file \u00b7 Overall: Counting every selected physical source record, as confirmed; repeated values on different sheets remain separate records.\nWhole file \u00b7 Overall \u00b7 BOLT-A \u2014 Quantity: 14 pcs. [1] [3]\nWhole file \u00b7 Overall \u00b7 NUT-B \u2014 Quantity: 14 pcs. [2] [4]\nWhole file \u00b7 BOLT-A: Total Quantity: 14 pcs. [1] [3]\nWhole file \u00b7 BOLT-A: Based on all 2 matching source records. The calculation evidence contains every operand.\nWhole file \u00b7 BOLT-A: Counting every selected physical source record, as confirmed; repeated values on different sheets remain separate records.\nWhole file \u00b7 BOLT-A \u00b7 BOLT-A \u2014 Quantity: 14 pcs. [1] [3]\nWhole file \u00b7 NUT-B: Total Quantity: 14 pcs. [2] [4]\nWhole file \u00b7 NUT-B: Based on all 2 matching source records. The calculation evidence contains every operand.\nWhole file \u00b7 NUT-B: Counting every selected physical source record, as confirmed; repeated values on different sheets remain separate records.\nWhole file \u00b7 NUT-B \u00b7 NUT-B \u2014 Quantity: 14 pcs. [2] [4]",
  answer_items: [
    {
      kind: "calculation",
      text: "Whole file \u00b7 Overall: Total Quantity: 28 pcs.",
      citation_numbers: [1, 2, 3, 4],
      record_number: null,
      scope: null,
    },
    {
      kind: "notice",
      text: "Whole file \u00b7 Overall: Based on all 4 matching source records. The calculation evidence contains every operand.",
      citation_numbers: [],
      record_number: null,
      scope: null,
    },
    {
      kind: "notice",
      text: "Whole file \u00b7 Overall: Counting every selected physical source record, as confirmed; repeated values on different sheets remain separate records.",
      citation_numbers: [],
      record_number: null,
      scope: null,
    },
    {
      kind: "notice",
      text: "Whole file \u00b7 Overall \u00b7 BOLT-A \u2014 Quantity: 14 pcs.",
      citation_numbers: [1, 3],
      record_number: null,
      scope: null,
    },
    {
      kind: "notice",
      text: "Whole file \u00b7 Overall \u00b7 NUT-B \u2014 Quantity: 14 pcs.",
      citation_numbers: [2, 4],
      record_number: null,
      scope: null,
    },
    {
      kind: "calculation",
      text: "Whole file \u00b7 BOLT-A: Total Quantity: 14 pcs.",
      citation_numbers: [1, 3],
      record_number: null,
      scope: null,
    },
    {
      kind: "notice",
      text: "Whole file \u00b7 BOLT-A: Based on all 2 matching source records. The calculation evidence contains every operand.",
      citation_numbers: [],
      record_number: null,
      scope: null,
    },
    {
      kind: "notice",
      text: "Whole file \u00b7 BOLT-A: Counting every selected physical source record, as confirmed; repeated values on different sheets remain separate records.",
      citation_numbers: [],
      record_number: null,
      scope: null,
    },
    {
      kind: "notice",
      text: "Whole file \u00b7 BOLT-A \u00b7 BOLT-A \u2014 Quantity: 14 pcs.",
      citation_numbers: [1, 3],
      record_number: null,
      scope: null,
    },
    {
      kind: "calculation",
      text: "Whole file \u00b7 NUT-B: Total Quantity: 14 pcs.",
      citation_numbers: [2, 4],
      record_number: null,
      scope: null,
    },
    {
      kind: "notice",
      text: "Whole file \u00b7 NUT-B: Based on all 2 matching source records. The calculation evidence contains every operand.",
      citation_numbers: [],
      record_number: null,
      scope: null,
    },
    {
      kind: "notice",
      text: "Whole file \u00b7 NUT-B: Counting every selected physical source record, as confirmed; repeated values on different sheets remain separate records.",
      citation_numbers: [],
      record_number: null,
      scope: null,
    },
    {
      kind: "notice",
      text: "Whole file \u00b7 NUT-B \u00b7 NUT-B \u2014 Quantity: 14 pcs.",
      citation_numbers: [2, 4],
      record_number: null,
      scope: null,
    },
  ],
  evidence_text:
    "Whole file \u00b7 Overall: Total Quantity: 28 pcs. [1] [2] [3] (+1 source records in evidence)\nWhole file \u00b7 Overall: Based on all 4 matching source records. The calculation evidence contains every operand.\nWhole file \u00b7 Overall: Counting every selected physical source record, as confirmed; repeated values on different sheets remain separate records.\nWhole file \u00b7 Overall \u00b7 BOLT-A \u2014 Quantity: 14 pcs. [1] [3]\nWhole file \u00b7 Overall \u00b7 NUT-B \u2014 Quantity: 14 pcs. [2] [4]\nWhole file \u00b7 BOLT-A: Total Quantity: 14 pcs. [1] [3]\nWhole file \u00b7 BOLT-A: Based on all 2 matching source records. The calculation evidence contains every operand.\nWhole file \u00b7 BOLT-A: Counting every selected physical source record, as confirmed; repeated values on different sheets remain separate records.\nWhole file \u00b7 BOLT-A \u00b7 BOLT-A \u2014 Quantity: 14 pcs. [1] [3]\nWhole file \u00b7 NUT-B: Total Quantity: 14 pcs. [2] [4]\nWhole file \u00b7 NUT-B: Based on all 2 matching source records. The calculation evidence contains every operand.\nWhole file \u00b7 NUT-B: Counting every selected physical source record, as confirmed; repeated values on different sheets remain separate records.\nWhole file \u00b7 NUT-B \u00b7 NUT-B \u2014 Quantity: 14 pcs. [2] [4]",
  citations: [
    {
      number: 1,
      source_file: "operations.pdf",
      sheet_or_page: "page_1",
      row_or_location: "table_1_row_1",
      citation_text: "operations.pdf / page_1 / row table_1_row_1",
    },
    {
      number: 2,
      source_file: "operations.pdf",
      sheet_or_page: "page_1",
      row_or_location: "table_1_row_2",
      citation_text: "operations.pdf / page_1 / row table_1_row_2",
    },
    {
      number: 3,
      source_file: "operations.pdf",
      sheet_or_page: "page_3",
      row_or_location: "table_1_row_1",
      citation_text: "operations.pdf / page_3 / row table_1_row_1",
    },
    {
      number: 4,
      source_file: "operations.pdf",
      sheet_or_page: "page_3",
      row_or_location: "table_1_row_2",
      citation_text: "operations.pdf / page_3 / row table_1_row_2",
    },
  ],
  unresolved_citation_numbers: [],
  context_count: 4,
  model: null,
  generation_latency_seconds: 0.0,
};
export const products = productsSpecimen as Answer;
const absentProductSpecimen = {
  workspace_revision: 0,
  resolved_question: "What is the quantity of Apple in the file?",
  clarification_options: [],
  status: "no_evidence",
  execution_path: "structured",
  records: [],
  coverage: {
    scope_records: 4,
    matched_records: 0,
    returned_records: 0,
    fields: ["Quantity"],
    complete: true,
    requested_entity: "Apple",
    entity_field: "Product",
    resolved_scopes: [],
  },
  calculation: null,
  grouped_results: [],
  warnings: [],
  timings_seconds: {
    total: 0.0007053510016703513,
  },
  answer:
    "No matching Product records were found for 'Apple' in operations.pdf.",
  answer_items: [],
  evidence_text: null,
  citations: [],
  unresolved_citation_numbers: [],
  context_count: 0,
  model: null,
  generation_latency_seconds: 0.0,
};
export const absentProduct = absentProductSpecimen as Answer;
const hoursSubtotalSpecimen = {
  workspace_revision: 0,
  resolved_question: "What is the sum of Hours?",
  clarification_options: [],
  status: "incomplete",
  execution_path: "structured",
  records: [
    {
      number: 1,
      source_file: "hours.xlsx",
      sheet_or_page: "Work log",
      row_or_location: 2,
      values: {
        Unit: "hours",
        Name: "Asha",
        Hours: "7.5",
      },
      cell_references: {
        Unit: "C2",
        Name: "A2",
        Hours: "B2",
      },
      merged_fields: [],
      cell_formats: {
        Hours: "0.00",
      },
      formula_fields: {},
      continuation_fields: {},
    },
    {
      number: 2,
      source_file: "hours.xlsx",
      sheet_or_page: "Work log",
      row_or_location: 3,
      values: {
        Unit: "hours",
        Name: "Asha",
        Hours: "8.25",
      },
      cell_references: {
        Unit: "C3",
        Name: "A3",
        Hours: "B3",
      },
      merged_fields: [],
      cell_formats: {
        Hours: "0.00",
      },
      formula_fields: {},
      continuation_fields: {},
    },
    {
      number: 3,
      source_file: "hours.xlsx",
      sheet_or_page: "Work log",
      row_or_location: 4,
      values: {
        Unit: "hours",
        Name: "Ben",
        Hours: null,
      },
      cell_references: {
        Unit: "C4",
        Name: "A4",
        Hours: "B4",
      },
      merged_fields: [],
      cell_formats: {
        Hours: "0.00",
      },
      formula_fields: {},
      continuation_fields: {},
    },
    {
      number: 4,
      source_file: "hours.xlsx",
      sheet_or_page: "Work log",
      row_or_location: 5,
      values: {
        Unit: "hours",
        Name: "Asha",
        Hours: "0",
      },
      cell_references: {
        Unit: "C5",
        Name: "A5",
        Hours: "B5",
      },
      merged_fields: [],
      cell_formats: {
        Hours: "0.00",
      },
      formula_fields: {},
      continuation_fields: {},
    },
  ],
  coverage: {
    method: "all_indexed_rows",
    record_scope: "auto",
    scope_records: 4,
    matched_records: 4,
    returned_records: 4,
    fields: ["Hours"],
    missing_cells: [
      {
        number: 3,
        field: "Hours",
        cell: "B4",
      },
    ],
    complete: false,
    calculation_complete: false,
    calculation_included_records: 3,
    calculation_excluded_cells: 1,
    resolved_scopes: [],
    page: 1,
    total_pages: 1,
    page_size: 50,
    calculation_uses_all_matches: false,
  },
  calculation: {
    operation: "sum",
    fields: ["Hours"],
    unit: "hours",
    rounding: "Exact decimal operands; no rounding",
    result: {
      Hours: "15.75",
    },
    operands: [
      {
        number: 1,
        values: {
          Hours: "7.5",
        },
        source: {
          source_file: "hours.xlsx",
          sheet_or_page: "Work log",
          row_or_location: 2,
        },
        cell_references: {
          Hours: "B2",
        },
      },
      {
        number: 2,
        values: {
          Hours: "8.25",
        },
        source: {
          source_file: "hours.xlsx",
          sheet_or_page: "Work log",
          row_or_location: 3,
        },
        cell_references: {
          Hours: "B3",
        },
      },
      {
        number: 4,
        values: {
          Hours: "0",
        },
        source: {
          source_file: "hours.xlsx",
          sheet_or_page: "Work log",
          row_or_location: 5,
        },
        cell_references: {
          Hours: "B5",
        },
      },
    ],
    partial: true,
    excluded_cells: [
      {
        number: 3,
        field: "Hours",
        cell: "B4",
        reason: "missing_value",
        source: {
          source_file: "hours.xlsx",
          sheet_or_page: "Work log",
          row_or_location: 4,
        },
      },
    ],
    matched_records: 4,
    included_records: 3,
    population_basis: "auto",
  },
  grouped_results: [],
  warnings: [
    "Available-value subtotal: 3 of 4 source records contribute; 1 requested source cells are missing and excluded. Missing values were not replaced with zero.",
  ],
  timings_seconds: {
    total: 0.0009536929992464138,
  },
  answer:
    "Available-value subtotal Hours: 15.75 hours. [1] [2] [4]\nIncluded source records: 3 of 4. Missing source cells excluded: 1. This is a subtotal, not a complete total; missing values were not replaced with zero.\nExcluded Work log / B4 \u2014 Hours: missing in source. [3]",
  answer_items: [
    {
      kind: "calculation",
      text: "Available-value subtotal Hours: 15.75 hours.",
      citation_numbers: [1, 2, 4],
      record_number: null,
      scope: null,
    },
    {
      kind: "notice",
      text: "Included source records: 3 of 4. Missing source cells excluded: 1. This is a subtotal, not a complete total; missing values were not replaced with zero.",
      citation_numbers: [],
      record_number: null,
      scope: null,
    },
    {
      kind: "notice",
      text: "Excluded Work log / B4 \u2014 Hours: missing in source.",
      citation_numbers: [3],
      record_number: null,
      scope: null,
    },
  ],
  evidence_text:
    "- hours.xlsx / Work log / row 2 \u2014 Unit: hours; Name: Asha; Hours: 7.5 (Source: [1])\n- hours.xlsx / Work log / row 3 \u2014 Unit: hours; Name: Asha; Hours: 8.25 (Source: [2])\n- hours.xlsx / Work log / row 4 \u2014 Unit: hours; Name: Ben; Hours: Missing in source (Source: [3])\n- hours.xlsx / Work log / row 5 \u2014 Unit: hours; Name: Asha; Hours: 0 (Source: [4])\nSubtotals: Hours = 15.75",
  citations: [
    {
      number: 1,
      source_file: "hours.xlsx",
      sheet_or_page: "Work log",
      row_or_location: 2,
      citation_text: "hours.xlsx / Work log / row 2",
    },
    {
      number: 2,
      source_file: "hours.xlsx",
      sheet_or_page: "Work log",
      row_or_location: 3,
      citation_text: "hours.xlsx / Work log / row 3",
    },
    {
      number: 3,
      source_file: "hours.xlsx",
      sheet_or_page: "Work log",
      row_or_location: 4,
      citation_text: "hours.xlsx / Work log / row 4",
    },
    {
      number: 4,
      source_file: "hours.xlsx",
      sheet_or_page: "Work log",
      row_or_location: 5,
      citation_text: "hours.xlsx / Work log / row 5",
    },
  ],
  unresolved_citation_numbers: [],
  context_count: 4,
  model: null,
  generation_latency_seconds: 0.0,
};
export const hoursSubtotal = hoursSubtotalSpecimen as Answer;
