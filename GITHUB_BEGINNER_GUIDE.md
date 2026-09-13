# Push Phase 1 to GitHub — beginner guide

## 1. Create the GitHub repository
On GitHub, create a new empty repository, for example:

`ai-clinic-receptionist-phase1`

Do not add a README, `.gitignore`, or license from GitHub because this project already contains them.

## 2. Open the project terminal in VS Code
Make sure the terminal is inside the project root — the folder containing `app`, `data`, `tests`, `streamlit_app.py`, and `requirements.txt`.

Check:

```powershell
Get-ChildItem
```

## 3. Initialize Git

```powershell
git init
git branch -M main
git status
```

## 4. Confirm sensitive/runtime files are ignored

```powershell
git status --ignored
```

You should **not** commit `.env`, `.venv`, `storage/clinic.db`, `__pycache__`, or `.pytest_cache`.

## 5. Make the first commit

```powershell
git add .
git status
git commit -m "Complete Phase 1 AI clinic receptionist"
```

## 6. Connect the GitHub repository
Replace `YOUR_USERNAME` with your GitHub username:

```powershell
git remote add origin https://github.com/YOUR_USERNAME/ai-clinic-receptionist-phase1.git
git remote -v
```

## 7. Push

```powershell
git push -u origin main
```

GitHub may open a browser for authentication. Do not put a GitHub password or access token inside your source code.

## 8. Future updates
After changing code:

```powershell
pytest -q
git status
git add .
git commit -m "Improve Phase 1 clinic assistant"
git push
```

## 9. What should appear on GitHub?
You should see:
- `app/`
- `data/`
- `evaluation/`
- `scripts/`
- `tests/`
- `streamlit_app.py`
- `requirements.txt`
- README files
- `.gitignore`

Runtime SQLite and local environment files should remain local.
