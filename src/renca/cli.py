from pathlib import Path
import pandas as pd
import typer
from renca.models import load_project_spec
from renca.runner import run_analysis
app=typer.Typer()
@app.command()
def run(config:Path=typer.Option(...),data:Path=typer.Option(...),output:Path=typer.Option(...)):
    try: run_analysis(pd.read_csv(data),load_project_spec(config),output)
    except Exception as error: raise typer.Exit(code=typer.echo(str(error),err=True) or 1)
