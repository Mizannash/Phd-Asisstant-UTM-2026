import ast
import os
import sys
import importlib

def get_all_imports(directory):
    imports = set()
    for root, _, files in os.walk(directory):
        for file in files:
            if file.endswith('.py'):
                path = os.path.join(root, file)
                with open(path, 'r', encoding='utf-8') as f:
                    try:
                        tree = ast.parse(f.read(), filename=path)
                        for node in ast.walk(tree):
                            if isinstance(node, ast.Import):
                                for n in node.names:
                                    imports.add(n.name.split('.')[0])
                            elif isinstance(node, ast.ImportFrom):
                                if node.module:
                                    imports.add(node.module.split('.')[0])
                    except Exception as e:
                        print(f"Error parsing {path}: {e}")
    return imports

std_libs = set(sys.builtin_module_names) | {'os', 'sys', 'json', 'glob', 'ast', 'datetime', 'time', 'traceback', 'subprocess', 'argparse', 'logging', 'pathlib', 'typing', 're', 'shutil', 'random', 'concurrent', 'warnings'}

def main():
    src_dir = r"D:\PhD_Assistant_UTM\src"
    all_imports = get_all_imports(src_dir)
    third_party = [m for m in all_imports if m not in std_libs and not m.startswith('src') and m not in ['config', 'quota_manager', 'logger', 'dashboard', 'scout', 'tools', 'agents']]
    
    missing = []
    for m in third_party:
        try:
            importlib.import_module(m)
        except ImportError:
            missing.append(m)
            
    print("Found third-party imports:", sorted(third_party))
    if missing:
        print("MISSING:", missing)
    else:
        print("ALL_IMPORTS_OK")

if __name__ == "__main__":
    main()
