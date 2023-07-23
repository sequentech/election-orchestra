{ pkgs, config, lib, ... }:

{
  # https://devenv.sh/basics/
  env.GREET = "devenv";

  # https://devenv.sh/packages/
  packages = lib.optionals (!config.container.isBuilding) [
    pkgs.git
    pkgs.ack

    # to create containers
    pkgs.docker

    # used for building uwsgi:
    pkgs.gcc
    pkgs.libffi
  ];

  # https://devenv.sh/processes/
  processes.election-orchestra.exec = ''
  devenv shell bash -c \
    "export FRESTQ_SETTINGS=base_settings.py &&\
     python app.py --createdb \
     && python app.py"
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
    # using python39 as default (python310) seems to have some glibc glitch
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
