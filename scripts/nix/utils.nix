{ lib, ... }:
{ 
  # Load env-file and convert its contents to a Nix set (dictionary)
  # Example usage:
  # loadEnv "/path/to/your/.env"
  loadEnv = filePath:
    let
      envContent = lib.fileContents(filePath);
      nonEmptyLines = builtins.filter
        (line: line != "")
        (lib.splitString "\n" envContent);
      keyValues = builtins.map
        (
          line:
            let 
              splitLine = lib.splitString "=" line;
            in {
              name = builtins.head (splitLine);
              value = lib.last (splitLine);
            }
        )
        nonEmptyLines;
    in
      lib.listToAttrs keyValues;
}