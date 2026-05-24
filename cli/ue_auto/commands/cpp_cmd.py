import argparse
import textwrap
from pathlib import Path
from typing import Callable

import yaml

from ue_auto import result as result_mod


# ── spec loading ──────────────────────────────────────────────────────────────

def parse_spec(path: str) -> dict:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Spec not found: {path}")
    data = yaml.safe_load(p.read_text())
    if not isinstance(data, dict) or "class" not in data:
        raise ValueError("Spec must have a top-level 'class' key")
    data.setdefault("properties", [])
    data.setdefault("functions", [])
    return data


# ── declaration builders ──────────────────────────────────────────────────────

def _build_macro_args(metadata: dict) -> str:
    parts: list[str] = []
    for k, v in metadata.items():
        if k == "Category":
            parts.append(f'Category = "{v}"')
        elif v is True:
            parts.append(k)
        elif v is not False:
            parts.append(f"{k} = {v}")
    return ", ".join(parts)


def build_property_decl(prop: dict) -> str:
    meta_args = _build_macro_args(prop.get("metadata", {}))
    macro = f"UPROPERTY({meta_args})" if meta_args else "UPROPERTY()"
    return f"\t{macro}\n\t{prop['type']} {prop['name']};"


def build_function_decl(fn: dict) -> str:
    meta_args = _build_macro_args(fn.get("metadata", {}))
    macro = f"UFUNCTION({meta_args})" if meta_args else "UFUNCTION()"
    params = ", ".join(f"{p['type']} {p['name']}" for p in fn.get("params", []))
    return f"\t{macro}\n\t{fn['return_type']} {fn['name']}({params});"


# ── prefix helpers ────────────────────────────────────────────────────────────

_TYPE_PREFIX = {
    "Actor": "A",
    "ActorComponent": "U",
    "DataAsset": "U",
    "Interface": None,  # special — two classes
}


def _api_macro(module: str) -> str:
    return f"{module.upper()}_API"


# ── header generators ─────────────────────────────────────────────────────────

def _header_actor(cls: dict, props: list[dict], fns: list[dict]) -> str:
    name = cls["name"]
    module = cls.get("module", "GAME")
    api = _api_macro(module)
    tick = cls.get("tick", True)
    prop_lines = "\n".join(build_property_decl(p) for p in props)
    fn_lines = "\n".join(build_function_decl(f) for f in fns)
    tick_decl = "\n\tvirtual void Tick(float DeltaTime) override;" if tick else ""

    return textwrap.dedent(f"""\
        #pragma once

        #include "CoreMinimal.h"
        #include "GameFramework/Actor.h"
        #include "{name}.generated.h"

        UCLASS(BlueprintType, Blueprintable)
        class {api} A{name} : public AActor
        {{
        \tGENERATED_BODY()
        public:
        \tA{name}();

        protected:
        \tvirtual void BeginPlay() override;
        public:{tick_decl}

        {"// Properties" if props else ""}
        {prop_lines}

        {"// Functions" if fns else ""}
        {fn_lines}
        }};
        """)


def _header_component(cls: dict, props: list[dict], fns: list[dict]) -> str:
    name = cls["name"]
    module = cls.get("module", "GAME")
    api = _api_macro(module)
    tick = cls.get("tick", False)
    prop_lines = "\n".join(build_property_decl(p) for p in props)
    fn_lines = "\n".join(build_function_decl(f) for f in fns)
    tick_decl = (
        "\n\tvirtual void TickComponent(float DeltaTime, ELevelTick TickType, "
        "FActorComponentTickFunction* ThisTickFunction) override;"
        if tick else ""
    )

    return textwrap.dedent(f"""\
        #pragma once

        #include "CoreMinimal.h"
        #include "Components/ActorComponent.h"
        #include "{name}.generated.h"

        UCLASS(ClassGroup=(Custom), meta=(BlueprintSpawnableComponent))
        class {api} U{name} : public UActorComponent
        {{
        \tGENERATED_BODY()
        public:
        \tU{name}();

        protected:
        \tvirtual void BeginPlay() override;
        public:{tick_decl}

        {"// Properties" if props else ""}
        {prop_lines}

        {"// Functions" if fns else ""}
        {fn_lines}
        }};
        """)


def _header_dataasset(cls: dict, props: list[dict], fns: list[dict]) -> str:
    name = cls["name"]
    module = cls.get("module", "GAME")
    api = _api_macro(module)
    prop_lines = "\n".join(build_property_decl(p) for p in props)

    return textwrap.dedent(f"""\
        #pragma once

        #include "CoreMinimal.h"
        #include "Engine/DataAsset.h"
        #include "{name}.generated.h"

        UCLASS(BlueprintType)
        class {api} U{name} : public UPrimaryDataAsset
        {{
        \tGENERATED_BODY()
        public:
        \tU{name}();

        {"// Properties" if props else ""}
        {prop_lines}
        }};
        """)


def _header_interface(cls: dict, props: list[dict], fns: list[dict]) -> str:
    name = cls["name"]
    module = cls.get("module", "GAME")
    api = _api_macro(module)
    fn_lines = "\n".join(build_function_decl(f) for f in fns)

    return textwrap.dedent(f"""\
        #pragma once

        #include "CoreMinimal.h"
        #include "UObject/Interface.h"
        #include "{name}.generated.h"

        UINTERFACE(MinimalAPI, BlueprintType)
        class U{name} : public UInterface
        {{
        \tGENERATED_BODY()
        }};

        class {api} I{name}
        {{
        \tGENERATED_BODY()
        public:
        {"// Functions" if fns else ""}
        {fn_lines}
        }};
        """)


def generate_header(spec: dict) -> str:
    cls = spec["class"]
    props = spec.get("properties", [])
    fns = spec.get("functions", [])
    cls_type = cls.get("type", "Actor")

    _generators = {
        "Actor": _header_actor,
        "ActorComponent": _header_component,
        "DataAsset": _header_dataasset,
        "Interface": _header_interface,
    }
    gen = _generators.get(cls_type)
    if gen is None:
        raise ValueError(f"Unknown class type: {cls_type}")
    return gen(cls, props, fns)


# ── source generators ─────────────────────────────────────────────────────────

def _source_actor(cls: dict, fns: list[dict]) -> str:
    name = cls["name"]
    tick = cls.get("tick", True)
    tick_body = textwrap.dedent(f"""
        void A{name}::Tick(float DeltaTime)
        {{
        \tSuper::Tick(DeltaTime);
        }}
        """) if tick else ""

    return textwrap.dedent(f"""\
        #include "{name}.h"

        A{name}::A{name}()
        {{
        \tPrimaryActorTick.bCanEverTick = {"true" if tick else "false"};
        }}

        void A{name}::BeginPlay()
        {{
        \tSuper::BeginPlay();
        }}
        {tick_body}""")


def _source_component(cls: dict, fns: list[dict]) -> str:
    name = cls["name"]
    tick = cls.get("tick", False)
    tick_body = textwrap.dedent(f"""
        void U{name}::TickComponent(
        \tfloat DeltaTime, ELevelTick TickType, FActorComponentTickFunction* ThisTickFunction)
        {{
        \tSuper::TickComponent(DeltaTime, TickType, ThisTickFunction);
        }}
        """) if tick else ""

    return textwrap.dedent(f"""\
        #include "{name}.h"

        U{name}::U{name}()
        {{
        \tPrimaryComponentTick.bCanEverTick = {"true" if tick else "false"};
        }}

        void U{name}::BeginPlay()
        {{
        \tSuper::BeginPlay();
        }}
        {tick_body}""")


def _source_dataasset(cls: dict) -> str:
    name = cls["name"]
    return textwrap.dedent(f"""\
        #include "{name}.h"

        U{name}::U{name}()
        {{
        }}
        """)


def _source_interface(cls: dict) -> str:
    name = cls["name"]
    return textwrap.dedent(f"""\
        #include "{name}.h"
        """)


def generate_source(spec: dict) -> str:
    cls = spec["class"]
    fns = spec.get("functions", [])
    cls_type = cls.get("type", "Actor")

    if cls_type == "Actor":
        return _source_actor(cls, fns)
    if cls_type == "ActorComponent":
        return _source_component(cls, fns)
    if cls_type == "DataAsset":
        return _source_dataasset(cls)
    if cls_type == "Interface":
        return _source_interface(cls)
    raise ValueError(f"Unknown class type: {cls_type}")


# ── command ───────────────────────────────────────────────────────────────────

def _cmd_generate_class(args) -> int:
    spec_path = getattr(args, "spec", None)
    out_dir = getattr(args, "out", None) or "."
    dry_run = getattr(args, "dry_run", True)
    apply = getattr(args, "apply", False)
    if apply:
        dry_run = False

    if not spec_path:
        r = result_mod.failure(
            "generate-class", "MISSING_SPEC", "--spec is required",
            hint="Pass --spec path/to/class.spec.yaml",
        )
        result_mod.write(r, getattr(args, "result", None))
        return 1

    try:
        spec = parse_spec(spec_path)
    except (FileNotFoundError, ValueError) as exc:
        r = result_mod.failure("generate-class", "SPEC_ERROR", str(exc))
        result_mod.write(r, getattr(args, "result", None))
        return 1

    name = spec["class"]["name"]
    header = generate_header(spec)
    source = generate_source(spec)

    out = Path(out_dir)
    h_path = out / f"{name}.h"
    cpp_path = out / f"{name}.cpp"

    mode = "DRY-RUN" if dry_run else "APPLY"
    print(f"{mode}  ue-auto cpp generate-class  ({name}.h / {name}.cpp → {out_dir})")

    if not dry_run:
        out.mkdir(parents=True, exist_ok=True)
        h_path.write_text(header, encoding="utf-8")
        cpp_path.write_text(source, encoding="utf-8")

    r = result_mod.success(
        "generate-class",
        f"{'Would generate' if dry_run else 'Generated'} {name}.h / {name}.cpp",
        snapshot=str(h_path) if not dry_run else None,
    )
    r["dry_run"] = dry_run
    r["files"] = [str(h_path), str(cpp_path)]
    result_mod.write(r, getattr(args, "result", None))
    return 0


# ── registration ──────────────────────────────────────────────────────────────

def register(
    sub: argparse.ArgumentParser,
    add_common: Callable[[argparse.ArgumentParser], None],
) -> None:
    gen_p = sub.add_parser("generate-class", help="Generate UE C++ class from YAML spec")
    add_common(gen_p)
    gen_p.add_argument("--spec", metavar="PATH", help="Class spec YAML path")
    gen_p.set_defaults(func=_cmd_generate_class)
