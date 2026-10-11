# Golden test — 329 Hobsonville Road Childcare Centre, Rev34E (excl. GST)

**Benchmark confirmed (Rick, 11 Oct 2026):** Rev34E is the current issue — Drive folder "Current Client Issue Pack Rev34E" (Rev34C and Rev34D folders are marked SUPERSEDED). Rev34F (14-Sep) was a presentation-only correction of the TPW schedule (CW/012 P&G $77,208.09 omitted visually); it changes no estimate or tender value and is not on Drive. Drive file ids: workbook 1oIV0Z3yomrz6-GydmOPdiMsP7RnBNX8i; basis report 1A2E8d4NkFIrziH3pxz3DA1C_TSmceN0C.

The platform must reproduce these figures from the same inputs. Source: `01_329_Hobsonville_Road_Estimate_Rev34E.xlsx`.

## Siteworks cost chain (Tender Build-Up)
| Item | Amount |
|---|---|
| PG01 Preliminaries & General | 48,403.40 |
| ESC01 Erosion & Sediment Control | 7,750.14 |
| Earthworks (EW01–EW10) | 116,065.18 |
| Pavements & Concrete | 119,034.31 |
| Kerbs, Channels & External Sitework | 65,000.00 |
| Retaining Walls | 71,668.84 |
| Testing, As-Builts & Compliance | 4,600.00 |
| Reinstatement & Handover | 3,000.00 |
| **Base direct estimate** | **435,521.88** |
| CA09 Dewatering (PC sum) | 3,000.00 |
| CA10 Weather allowance (Weather Engine) | 18,204.69 |
| CA16 Management Reserve (4% x 456,726.56) | 18,269.06 |
| **Pre-margin additions** | **39,473.75** |
| **Subtotal before commercial adjustments** | **474,995.63** |
| CA17 Overhead 10% markup on subtotal | 47,499.56 |
| CA18 Profit 15% TRUE MARGIN = (subtotal+OH)/(1-0.15) - (subtotal+OH) | 92,205.03 |
| **Siteworks standalone tender** | **614,700.22** |

## Consolidated package
| Item | Amount |
|---|---|
| Siteworks pre-commercial (incl. MR) | 474,995.63 |
| Coast Concrete subcontract (quoted) | 210,606.00 |
| Allied drainage combined (public 174,758.71 + private 87,711.74) | 262,470.45 |
| **Current known cost before OH/profit** | **948,072.08** |
| Company OH 10% | 94,807.21 |
| Profit 15% true margin | 184,037.52 |
| **Working all-in tender** | **1,226,916.81** |
| Gross margin on sell | 22.73% |

Checks: 948,072.08 x 1.10 / 0.85 = 1,226,916.81. 474,995.63 x 1.10 / 0.85 = 614,700.22. Allied private allocation must equal attachment total 87,711.74 (difference zero).

## Weather engine (CA10), start 2026-10-01, 55 baseline working days, Auckland/Whenuapai NIWA 1991–2020 normals
- Weather-exposed labour + plant pool: 54,070.63 (tool run basis)
- Rain/wet-ground direct productivity output: 12,458.56 (23.04% rate); live link = output x (current exposed pool / tool-run pool)
- Critical-path weather delay: 8.829 WD; time-related prelims = delay x (supervisor rate x 8h) = 8.829 x 584 = 5,156.13
- Additional billed hire weeks: 2 x 295 = 590.00
- Recovery/remediation default 0; wind proxy excluded (sensitivity only)
- **CA10 = 12,458.56 + 5,156.13 + 590.00 + 0 = 18,204.69**. Dry programme 55 WD; weather-adjusted ~63.8 WD.

## Status/gates that must be reproduced
Release status CONTRACT-AWARD HOLD (technical REDs remain; Risk Truth gate "HOLD - RED ITEMS": 4 RED risks, 3 RED exposures; duplicate-cost gate OK; programme dependency gate OK; current tender equals Risk Truth recalculation: YES).

## Known data quirks the platform should surface, not hide
- Allied email-body total typo vs attachment ($87,711.74 attachment is source of truth).
- Weather manual PC reference 18,000 vs live engine 18,204.69 (difference -204.69; live engine governs).
- Bulk earthworks mass balance conflict (RFI-15): 110 m3 cut, 1,033 m3 fill, 923 m3 net import.

## Still to extract for full line-level golden test
QS Takeoff lines (rows 3–40), Resource Build-Up rows 7–306 (5,349 formulas), Resource Rate Library (81 codes), Rate Verification (130 rows), Risk Truth register, ERB tabs. Do this by script from the workbook, with Rick's permission to hold a private copy.
