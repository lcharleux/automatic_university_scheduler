import yaml
import shutil
from automatic_university_scheduler.utils import Messages

db_info = yaml.safe_load(open("setup.yaml"))
shutil.rmtree(db_info["output_dir"], ignore_errors=True)
print(f"Output directory removed => {Messages.SUCCESS}")
