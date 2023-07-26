{ pkgs, config, lib, ... }:

{
  packages = [
    pkgs.git
    pkgs.ack

    # to create containers
    pkgs.docker

    # to inspect containers
    pkgs.dive

    # used for building uwsgi (TODO: deprecated):
    pkgs.gcc
    pkgs.libffi
  ];

  # HACK: I had to use `python $DEVENV_STATE/venv/bin/flask` instead of simply
  #       `flask` because otherwise it fails for some reason.
  processes.serve.exec = (
    ''
    export FLASK_ENV=development
    export FLASK_APP=election_orchestra.app:app
    export PYTHONPATH="$DEVENV_STATE/venv/lib/python3.10/site-packages:$PYTHONPATH"
    export FRESTQ_SETTINGS=base_settings.py
    python election_orchestra/app.py --createdb
    ''
    # + (if (config.container.isBuilding)
    #   then "python $DEVENV_STATE/venv/bin/flask run"
    #   else "flask run"
    # )
  );

  # HACK: The venv is missing from PYTHONPATH and PATH so I add them manually
  enterShell = (
    ''git --version;''
    + (
      lib.optionalString (config.container.isBuilding) 
      ''export PYTHONPATH="$DEVENV_STATE/venv/lib/python3.10/site-packages:$PYTHONPATH"''
    )
  );

  # https://devenv.sh/languages/
  languages.nix.enable = true;
  languages.python = {
    enable = true;
    poetry = {
      enable = true;
    };
  };

  services.postgres = {
    enable = true;
    package = pkgs.postgresql_15;
    initialDatabases = [{ name = "election-orchestra"; }];
  };
}