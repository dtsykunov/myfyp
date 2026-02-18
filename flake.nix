{
  description = "myfyp development shell";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
  };

  outputs =
    { self, nixpkgs }:
    let
      systems = [
        "x86_64-linux"
        "aarch64-linux"
      ];
      forEachSystem = nixpkgs.lib.genAttrs systems;
    in
    {
      devShells = forEachSystem (
        system:
        let
          pkgs = import nixpkgs { inherit system; };
          python = pkgs.python313.withPackages (
            ps: with ps; [
              fastapi
              httpx
              pytest
              pytest-cov
              ruff
              uvicorn
            ]
          );
        in
        {
          default = pkgs.mkShell {
            packages = [
              python
              pkgs.pyright
              pkgs.docker
              pkgs.docker-compose
              pkgs.zip
            ];

            shellHook = ''
              repo_root="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
              export PYTHONPATH="$repo_root/api/src${PYTHONPATH:+:$PYTHONPATH}"
              echo "myfyp dev shell loaded."
              echo "Run: cd api && ./scripts/run-tests.sh"
            '';
          };
        }
      );
    };
}
