from .sodermaklarna import Sodermaklarna
from .bjurfors import Bjurfors
from .maklarhuset import Maklarhuset
from .skandiamaklarna import Skandiamaklarna
from .fastighetsbyran import Fastighetsbyran
from .svenskfast import Svenskfast
from .boneo import Boneo

ALL_SCRAPERS = [
    Sodermaklarna,
    Bjurfors,
    Maklarhuset,
    Skandiamaklarna,
    Fastighetsbyran,
    Svenskfast,
    Boneo,
]

__all__ = ['ALL_SCRAPERS']
