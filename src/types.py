from typing import List, Optional, TypedDict


class StudentInfo(TypedDict):
    name: str
    uin: str
    netid: str

class GradeEntry(TypedDict):
    name: str
    type: str
    score: float
    min: float
    q1: float
    median: float
    q3: float
    max: float
    mean: float
    std: float
    bins: Optional[List]