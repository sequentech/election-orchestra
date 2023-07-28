{ pkgs, config, lib, ... }:

{
  packages = [
    pkgs.git
    pkgs.ack

    # used in eotest
    pkgs.nodejs

    # to create containers
    pkgs.docker

    # to inspect containers
    pkgs.dive
  ];

  # HACK: I had to use `python $DEVENV_STATE/venv/bin/flask` instead of simply
  #       `flask` because otherwise it fails for some reason.
  processes.serve.exec = (
    ''
    set -eux
    export FLASK_ENV=development
    export FLASK_APP=election_orchestra.app:app
    export PYTHONPATH="/workspace:$VIRTUAL_ENV/lib/python3.10/site-packages/:$PYTHONPATH"
    export EO_SQLALCHEMY_DATABASE_URI="postgresql+psycopg2:///dev"
    timeout 20 bash -c 'until psql -c "SELECT 1" dev; do sleep 0.5; done'
    python -m election_orchestra.app --createdb
    flask run
    ''
    # flask run
    # ''
  );

  # HACK: The venv is missing from PYTHONPATH and PATH so I add them manually
  enterShell = ''git --version;'';

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
    initialScript = ''
    CREATE USER dev WITH PASSWORD 'dev' SUPERUSER;
    '';
    initialDatabases = [{ name = "dev"; }];
  };
}