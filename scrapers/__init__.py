from .sodermaklarna import Sodermaklarna
from .bjurfors import Bjurfors
from .maklarhuset import Maklarhuset
from .skandiamaklarna import Skandiamaklarna
from .fastighetsbyran import Fastighetsbyran
from .svenskfast import Svenskfast
from .boneo import Boneo
from .historiskahem import Historiskahem
from .bosthlm import Bosthlm

ALL_SCRAPERS = [
    Sodermaklarna,
    Bjurfors,
    Maklarhuset,
    Skandiamaklarna,
    Fastighetsbyran,
    Svenskfast,
    Boneo,
    Historiskahem,
    Bosthlm,
]

__all__ = ['ALL_SCRAPERS']
