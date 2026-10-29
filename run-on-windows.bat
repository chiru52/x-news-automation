@echo off
cd /d "%~dp0"
python -m unittest discover -s tests -v
python -m newsbot --demo --state .state/demo.json --output output/demo
echo See output\demo\review_queue.md
pause
