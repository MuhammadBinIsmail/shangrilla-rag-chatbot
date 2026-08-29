"""Fixed set of SAP modules covered by this project.

Confirmed closed set (Round 2 of the architecture doc): no new modules
are expected. If that ever changes, this is the one place to update -
nothing else in the pipeline should hardcode a module list.
"""
from enum import Enum


class Module(str, Enum):
    CO = "CO"
    FI = "FI"
    MM = "MM"
    PP = "PP"
    QM = "QM"
    TM = "TM"
    WM = "WM"
