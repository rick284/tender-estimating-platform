"""Client-facing outputs generated from a computed estimate (tender_engine.estimate.compute_estimate).

These functions only LAY OUT numbers the engine has already calculated; they never calculate prices themselves.
Needs openpyxl (workbook) and reportlab (PDFs), which are optional dependencies of the engine.
"""
from .pricing_workbook import pricing_workbook
from .report import report_pdf, schedule_pdf
from .context import OutputContext

__all__ = ["pricing_workbook", "report_pdf", "schedule_pdf", "OutputContext"]
