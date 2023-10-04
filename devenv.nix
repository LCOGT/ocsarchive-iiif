{ pkgs, ... }:

let
  # numpy et. al. need access to some shared libraries when installed from
  # outside Nix (ie. poetry/pip).
  # This is a hack by setting LD_LIBRARY_PATH. Makes the derivation "un-pure".
  # Mileage may vary.
  python = pkgs.symlinkJoin {
      name = "wrapped-python";
      paths = [ pkgs.python311 ];
      nativeBuildInputs = [ pkgs.makeWrapper ];
      postBuild = ''
        for f in $(find -L $out/bin/ -type f -executable); do
          wrapProgram "$f" \
            --suffix LD_LIBRARY_PATH : ${pkgs.lib.makeLibraryPath [ pkgs.zlib pkgs.stdenv.cc.cc ]}
        done
       '';

  };
in
{
  # See full reference at https://devenv.sh/reference/options/

  # https://devenv.sh/packages/
  packages = [
    pkgs.git
    pkgs.poetry
    pkgs.temporal-cli
    python
    pkgs.kustomize
    pkgs.skaffold
    pkgs.kubectl
    pkgs.kind
    pkgs.kubernetes-helm
  ];

  enterShell = ''
    export KUBECONFIG=`pwd`/kind-kubeconfig
  '';

  # https://devenv.sh/languages/
  languages.nix.enable = true;

}
