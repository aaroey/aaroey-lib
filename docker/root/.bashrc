AAROEY_LIB_DIR=$HOME/Workspace/aaroey/aaroey-lib
init_aaroey_lib() {
  if ! [[ -d $AAROEY_LIB_DIR ]]; then
    mkdir -p ${AAROEY_LIB_DIR%/*}
    git clone https://github.com/aaroey/aaroey-lib.git $AAROEY_LIB_DIR
    pushd $AAROEY_LIB_DIR
    git config user.name 'Guangda Lai'
    git config user.email 31743510+aaroey@users.noreply.github.com
    popd
  fi
  pushd $AAROEY_LIB_DIR
  git pull origin master
  source $AAROEY_LIB_DIR/config/common/bashrc
  popd
}
init_aaroey_lib
