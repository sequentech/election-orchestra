{ pkgs, config, lib, ... }:

{
  # https://devenv.sh/basics/
  env.GREET = "devenv";

  # https://devenv.sh/packages/
  packages = lib.optionals (!config.container.isBuilding) [
    pkgs.git
  ];

  # https://devenv.sh/processes/
  processes.election-orchestra.exec = """
  export FRESTQ_SETTINGS=base_settings.py
  python -m flask
  """;

  enterShell = ''
    git --version
  '';

  # https://devenv.sh/integrations/codespaces-devcontainer/
  devcontainer.enable = true;

  # https://devenv.sh/languages/
  languages.nix.enable = true;
  languages.python = {
    enable = true;
    venv.enable = true;
    venv.requirements = builtins.readFile ./requirements.txt;
  };

  services.postgres = {
    enable = true;
    package = pkgs.postgresql_15;
    initialDatabases = [{ name = "election-orchestra"; }];
  };
}
