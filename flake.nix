# SPDX-FileCopyrightText: 2023 Sequent Tech Inc <legal@sequentech.io>
# SPDX-License-Identifier: AGPL-3.0-only

# Usage:
# time nix run .#dockerImage.copyToDockerDaemon && docker images election_orchestra:latest && docker run -it --network election-orchestra_devcontainer_default election_orchestra:latest
# Then:
# curl http://172.18.0.3:9090
{
  description = "test-devenv test project";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    devenv.url = "github:cachix/devenv";

    nix2container.url = "github:nlewo/nix2container";
    nix2container.inputs.nixpkgs.follows = "nixpkgs";
    mk-shell-bin.url = "github:rrbutani/nix-mk-shell-bin";
    flake-parts.url = "github:hercules-ci/flake-parts";
    mixnet.url = "github:sequentech/mixnet/feat/master/k8s";

    # Get poetry2nix directly from the GitHub source to get an updated 
    # cryptography lib, see the following link for more info:
    # https://github.com/nix-community/poetry2nix/issues/413#issuecomment-1604998895
    poetry2nixFlake.url = "github:nix-community/poetry2nix";
  };

  nixConfig = {
    extra-trusted-public-keys = "devenv.cachix.org-1:w1cLUi8dv3hnoSPGAuibQv+f9TZLr6cv/Hm9XgU50cw=";
    extra-substituters = "https://devenv.cachix.org";
  };
  outputs = inputs@{ flake-parts, poetry2nixFlake, mixnet, ... }:
    flake-parts.lib.mkFlake { inherit inputs; } {
      imports = [
        inputs.devenv.flakeModule
      ];
      systems = [ "x86_64-linux" ];

      # Per-system attributes can be defined here. The self' and inputs'
      # module parameters provide easy access to attributes of the same
      # system.
      perSystem = perSystemInputs@{ config, self', inputs', pkgs, system, lib, ... }:
        let
          python = pkgs.python3;
          poetry2nix = poetry2nixFlake.legacyPackages.${pkgs.stdenv.system};
          nix2containerInput = inputs.nix2container;
          nix2container = nix2containerInput.packages.${pkgs.stdenv.system};
          mixnetPackages = mixnet.packages.${pkgs.stdenv.system};

          # <Fixes frestq build>
          # See https://github.com/nix-community/poetry2nix/blob/master/docs/edgecases.md#modulenotfounderror-no-module-named-packagename
          election_orchestra-build-requirements = {
            frestq = [ "poetry" ];
          };
          election_orchestra-overrides = poetry2nix.defaultPoetryOverrides.extend (
            self: super: builtins.mapAttrs 
              (package: build-requirements:
                (builtins.getAttr package super).overridePythonAttrs (old: {
                  buildInputs = 
                    (old.buildInputs or [ ])
                    ++ (
                      builtins.map 
                        (pkg: 
                          if (builtins.isString pkg) 
                          then (builtins.getAttr pkg super)
                          else pkg
                        )
                        build-requirements
                    );
                })
              )
              election_orchestra-build-requirements
          );
          # </Fixes frestq build>

          election_orchestra = poetry2nix.mkPoetryApplication {
            projectDir = ./.;
            python = python;
            overrides = election_orchestra-overrides;
          };
          servicePort = "9090";
          dockerImage = nix2container.nix2container.buildImage {
            name = "election_orchestra";
            tag = "latest";
            copyToRoot = pkgs.buildEnv {
              name = "root";
              paths = [ 
                pkgs.bashInteractive
                pkgs.coreutils
                pkgs.nodejs
                python.pkgs.gunicorn
                mixnetPackages.mixnet
                election_orchestra.dependencyEnv
              ];
              pathsToLink = [ "/bin" "/lib" ];
            };
            config = {
              entrypoint = [
                #"${election_orchestra.dependencyEnv}/bin/flask" "run"
                "${python.pkgs.gunicorn}/bin/gunicorn"
                "-b" "0.0.0.0:${servicePort}"
                "--log-level" "debug"
                "election_orchestra.app:app"
              ];
              Env = lib.mapAttrsToList (name: value: "${name}=${value}") {
                FLASK_APP = "election_orchestra.app:app";
                FLASK_RUN_PORT = "${servicePort}";
                FLASK_RUN_HOST = "0.0.0.0";
                PYTHONPATH = "${election_orchestra.dependencyEnv}/lib/python3.10/site-packages";
              };
              ExposedPorts  = {
                "${servicePort}/tcp" = {};
              };

            };
            # This is to not rebuild everything on code changes
            layers = [
              (nix2container.nix2container.buildLayer {
                deps = [
                  python.pkgs.gunicorn
                  pkgs.bashInteractive
                  pkgs.coreutils
                  pkgs.nodejs
                  mixnetPackages.mixnet
                ];
              })
              (nix2container.nix2container.buildLayer {
                deps = [
                  election_orchestra.dependencyEnv
                ];
              })
            ];
          };
        in {
          packages.election_orchestra = election_orchestra;
          packages.dockerImage = dockerImage;
          packages.default = election_orchestra;
        };
        flake = {
          # The usual flake attributes can be defined here, including system-
          # agnostic ones like nixosModule and system-enumerating ones, although
          # those are more easily expressed in perSystem.
        };
    };
}
