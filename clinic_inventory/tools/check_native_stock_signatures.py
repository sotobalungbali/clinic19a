"""Compare every local Stock/Product override against supplied native Odoo source."""
import ast
import json
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def attributes(cls):
    out={}
    for n in cls.body:
        if isinstance(n,ast.Assign):
            for t in n.targets:
                if isinstance(t,ast.Name) and t.id in ('_name','_inherit'):
                    try:out[t.id]=ast.literal_eval(n.value)
                    except ValueError:pass
    return out

def audit(native):
    classes={}
    for module in ['stock','product']:
        directory=native/module/'models'
        if not directory.is_dir():raise ValueError(f'Missing native source: {directory}')
        for p in directory.glob('*.py'):
            for cls in ast.parse(p.read_text()).body:
                if not isinstance(cls,ast.ClassDef):continue
                attrs=attributes(cls);model=attrs.get('_name',attrs.get('_inherit'))
                if isinstance(model,str):
                    for method in cls.body:
                        if isinstance(method,ast.FunctionDef):classes[(model,method.name)]=method
    rows=[]
    for p in (ROOT/'models').glob('*.py'):
        for cls in ast.parse(p.read_text()).body:
            if not isinstance(cls,ast.ClassDef):continue
            model=attributes(cls).get('_inherit')
            if not isinstance(model,str):continue
            for method in cls.body:
                if not isinstance(method,ast.FunctionDef) or (model,method.name) not in classes:continue
                native_method=classes[(model,method.name)]
                expected={x.arg for x in native_method.args.args[1:]+native_method.args.kwonlyargs}
                actual={x.arg for x in method.args.args[1:]+method.args.kwonlyargs}
                missing=expected-actual if not method.args.kwarg else set()
                rows.append(dict(model=model,method=method.name,native_keywords=sorted(expected),owner_keywords=sorted(actual),missing=sorted(missing)))
    return rows

if __name__=='__main__':
    rows=audit(Path(sys.argv[1]));print(json.dumps(rows,indent=2))
    sys.exit(1 if not rows or any(row['missing'] for row in rows) else 0)

