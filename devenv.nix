{ pkgs, config, lib, ... }:

{
  # https://devenv.sh/basics/
  env.GREET = "devenv";

  # https://devenv.sh/packages/
  packages = lib.optionals (!config.container.isBuilding) [
    pkgs.git
    pkgs.ack

    # used for building uwsgi:
    pkgs.gcc
    pkgs.libffi
  ];

  # https://devenv.sh/processes/
  processes.election-orchestra.exec = ''
  export FRESTQ_SETTINGS=base_settings.py
  devenv shell python app.py --createdb && python app.py
  '';

  enterShell = ''
    git --version
  '';

  # https://devenv.sh/integrations/codespaces-devcontainer/
  devcontainer.enable = true;

  # https://devenv.sh/languages/
  languages.nix.enable = true;
  languages.python = {
    enable = true;
    package = pkgs.python39;
    venv.enable = true;
    venv.requirements = (
      builtins.readFile ./requirements.txt + 
      ''
      colorama==0.4.6
      PyYAML==6.0.1
      ZODB==5.8.1
      '');
  };

  services.postgres = {
    enable = true;
    package = pkgs.postgresql_15;
    initialDatabases = [{ name = "election-orchestra"; }];
  };
}
