"""Vehicle Inspection models package.

Loads all model modules for the vehicle inspection addon, including
inspection records, checklist configuration, wizards, and fleet extensions.
"""

from . import inspection_category
from . import inspection_item
from . import inspection_line
from . import vehicle_inspection
from . import vehicle_fault_wizard
from . import vehicle_not_running_wizard
from . import vehicle_resolved_wizard
from . import vehicle_resolved_not_running_wizard
from . import fleet_vehicle

