"""Shared schema role descriptions for web/API reading audits.

No candidate edits, evidence completion or approval.
"""
def schema_contract(schema,pointer):
    """Resolve role descriptions without reading or modifying candidate values."""
    def expand(node):
        if '$ref' in node:
            target=schema
            for part in node['$ref'].removeprefix('#/').split('/'):
                target=target[part]
            return expand({**target,**{k:v for k,v in node.items() if k!='$ref'}})
        return [node,*[branch for key in ('anyOf','oneOf') for child in node.get(key,[]) for branch in expand(child)]]
    current=[schema];ancestors=[]
    for raw in pointer.split('/')[1:]:
        part=raw.replace('~1','/').replace('~0','~');following=[]
        for node in current:
            for branch in expand(node):
                if branch.get('description'):ancestors.append(branch['description'])
                child=branch.get('items') if part.isdigit() else branch.get('properties',{}).get(part)
                if isinstance(child,dict):following.append(child)
        current=following
    definitions=[];properties={}
    for node in current:
        for branch in expand(node):
            if branch.get('description'):definitions.append(branch['description'])
            for name,prop in branch.get('properties',{}).items():
                details=[{k:v for k,v in item.items() if k in ('description','enum','const','x-cfm-field-contract')}
                         for item in expand(prop)]
                properties[name]=[d for d in details if d]
    return dict(path=pointer,ancestor_definitions=list(dict.fromkeys(ancestors)),
                definitions=list(dict.fromkeys(definitions)),properties=properties)
