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
              pydantic
              pytest
              pytest-cov
              ruff
            ]
          );
        in
        {
          default = pkgs.mkShell {
            packages = [
              python
              pkgs.pyright
              pkgs.nodejs_22
              pkgs.docker
              pkgs.docker-compose
              pkgs.zip
              pkgs.uv
              pkgs.stdenv.cc.cc.lib
            ];

            shellHook = ''
              repo_root="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
              export LD_LIBRARY_PATH="${pkgs.lib.makeLibraryPath [ pkgs.stdenv.cc.cc.lib ]}''${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
              export PYTHONPATH="$repo_root/cloudflare/worker/src${PYTHONPATH:+:$PYTHONPATH}"
              echo "myfyp dev shell loaded."
              echo "Run: ./cloudflare/worker/scripts/run-tests.sh"
            '';
          };
        }
      );
    };
}
