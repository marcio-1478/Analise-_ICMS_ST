import os
import subprocess
import sys


def run_pip(args: list[str]) -> tuple[int, str]:
    cmd = [sys.executable, "-m", "pip"] + args
    proc = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
    )
    output = (proc.stdout or "") + (proc.stderr or "")
    return proc.returncode, output


def main() -> int:
    packages = ["pandas", "pdfplumber"]

    print(f"Python em uso: {sys.executable}")
    print("Instalando pacotes:", ", ".join(packages))

    code, output = run_pip(["install", *packages])
    print(output)
    if code == 0:
        print("Instalacao concluida com sucesso.")
        return 0

    if "permission" in output.lower() or "acesso negado" in output.lower():
        print("Erro de permissao detectado. Tentando novamente com --user...")
        code, output = run_pip(["install", "--user", *packages])
        print(output)
        return code

    return code


if __name__ == "__main__":
    raise SystemExit(main())
