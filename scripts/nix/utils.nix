{ lib, ... }:
{ 
  # Load env-file and convert its contents to a Nix set (dictionary)
  # Example usage:
  # loadEnv "/path/to/your/.env"
  # Note: It doesn't support multiline with """ nor quoting with "", but it does
  # support comments with #
  loadEnv = filePath:
    let
      envContent = lib.fileContents(filePath);
      assignmentLines = builtins.filter
        (line: line != "" && (builtins.match "^#.*" line) == null)
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
        assignmentLines;
    in
      lib.listToAttrs keyValues;
    
    # Similar to builtins.getAttr, but with a third parameter providing a 
    # default value to return if the attrKey is not inside the set 
    getAttrDefault = attrKey: set: default:
      if (set ? attrKey)
      then (set."${attrKey}")
      else default;
}