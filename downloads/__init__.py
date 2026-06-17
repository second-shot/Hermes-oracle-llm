"""Hermes V5 Download Brain package.

The Download Brain turns the user's Downloads folder into a deterministic intake
pipeline. It scans files, extracts safe metadata, classifies file types, routes
items to Hermes project domains, and persists a queue for later processing.
"""

from .intake import DownloadBrain, run_download_intake

__all__ = ["DownloadBrain", "run_download_intake"]
