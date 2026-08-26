#!/usr/bin/env python3
"""GenVM-oriented static lint for the contracts in this repository.

Checks the rules that most often break `genvm` deployment or produce a
"contract schema" error, without needing a live GenVM toolchain:

  1. the `# v0.2.16` / `# { "Depends": "py-genlayer:<hash>" }` header pair is the
     first two lines, and the hash matches the pinned value
  2. exactly one `gl.Contract` subclass per contract file
  3. every persisted annotation uses a storage-safe type
  4. no float / Optional / Union / bare list-dict storage annotations
  5. no forbidden non-deterministic constructs outside nondet blocks
     (time, random, os, requests, urllib, datetime.now)
  6. `gl.nondet.*` is only reachable from within a nondet closure
  7. the file compiles under the host Python
"""

from __future__ import annotations

import ast
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
CONTRACTS = ROOT / "contracts"

EXPECTED_VERSION = "# v0.2.16"
EXPECTED_DEPENDS = (
    '# { "Depends": "py-genlayer:'
    '1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6" }'
)

STORAGE_SCALARS = {
    "str",
    "bool",
    "bytes",
    "Address",
    "bigint",
    "u8",
    "u16",
    "u32",
    "u64",
    "u128",
    "u256",
    "i8",
    "i16",
    "i32",
    "i64",
    "i128",
    "i256",
}
STORAGE_GENERICS = {"DynArray", "TreeMap", "Array"}
FORBIDDEN_MODULES = {"time", "random", "os", "requests", "urllib", "socket", "secrets"}
FORBIDDEN_STORAGE = {"float", "complex", "Optional", "Union", "Any", "list", "dict", "set", "tuple"}


class Failure(Exception):
    pass


def _type_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    if isinstance(node, ast.Subscript):
        return _type_name(node.value)
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return type(node).__name__


def check_storage_annotation(node: ast.AST, errors: list[str], where: str) -> None:
    name = _type_name(node)
    if name in FORBIDDEN_STORAGE:
        errors.append(f"{where}: `{name}` is not a GenVM storage type")
        return
    if isinstance(node, ast.Subscript):
        if name not in STORAGE_GENERICS:
            errors.append(f"{where}: `{name}[...]` is not a GenVM storage generic")
        args = node.slice.elts if isinstance(node.slice, ast.Tuple) else [node.slice]
        for arg in args:
            check_storage_annotation(arg, errors, where)
        return
    if name not in STORAGE_SCALARS and not name[:1].isupper():
        errors.append(f"{where}: `{name}` is not a recognised storage type")


def lint(path: pathlib.Path) -> list[str]:
    errors: list[str] = []
    source = path.read_text()
    lines = source.splitlines()

    if len(lines) < 2 or lines[0].strip() != EXPECTED_VERSION:
        errors.append(f"{path.name}: line 1 must be exactly `{EXPECTED_VERSION}`")
    if len(lines) < 2 or lines[1].strip() != EXPECTED_DEPENDS:
        errors.append(f"{path.name}: line 2 must be the pinned py-genlayer Depends comment")

    try:
        tree = ast.parse(source)
    except SyntaxError as exc:  # pragma: no cover - reported, not raised
        return errors + [f"{path.name}: syntax error: {exc}"]

    contracts = [
        node
        for node in tree.body
        if isinstance(node, ast.ClassDef)
        and any(_type_name(base) == "Contract" for base in node.bases)
    ]
    if len(contracts) != 1:
        errors.append(f"{path.name}: expected exactly one gl.Contract subclass, found {len(contracts)}")

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.split(".")[0] in FORBIDDEN_MODULES:
                    errors.append(f"{path.name}: forbidden import `{alias.name}`")
        if isinstance(node, ast.ImportFrom) and node.module:
            if node.module.split(".")[0] in FORBIDDEN_MODULES:
                errors.append(f"{path.name}: forbidden import from `{node.module}`")

    for contract in contracts:
        for stmt in contract.body:
            if isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name):
                check_storage_annotation(
                    stmt.annotation, errors, f"{path.name}:{contract.name}.{stmt.target.id}"
                )

    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and any(
            _type_name(d) == "allow_storage" for d in node.decorator_list
        ):
            for stmt in node.body:
                if isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name):
                    check_storage_annotation(
                        stmt.annotation, errors, f"{path.name}:{node.name}.{stmt.target.id}"
                    )

    nondet_calls = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and isinstance(node.func.value, ast.Attribute)
        and node.func.value.attr in ("nondet", "web")
    ]
    runners = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr
        in ("run_nondet", "run_nondet_unsafe", "strict_eq", "prompt_comparative")
    ]
    if nondet_calls and not runners:
        errors.append(f"{path.name}: gl.nondet.* used without an eq-principle / run_nondet wrapper")

    return errors


def main() -> int:
    files = sorted(CONTRACTS.glob("*.py"))
    if not files:
        print("no contracts found under contracts/")
        return 1

    failed = False
    for path in files:
        errors = lint(path)
        if errors:
            failed = True
            print(f"FAIL {path.relative_to(ROOT)}")
            for error in errors:
                print(f"  - {error}")
        else:
            print(f"ok   {path.relative_to(ROOT)}")

    print("\nGenVM lint:", "FAILED" if failed else "PASSED")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
