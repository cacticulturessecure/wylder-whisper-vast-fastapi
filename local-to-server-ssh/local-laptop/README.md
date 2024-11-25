To use these scripts:

Create the directory structure:

bashCopymkdir -p ~/gpu-tunnel/{bin,config,logs,data/{outgoing,sent}}

Copy scripts to appropriate locations:

bashCopycp 01_local_setup.sh 02_local_transfer.sh test_json_transfer.sh verify_setup.sh ~/gpu-tunnel/bin/
chmod +x ~/gpu-tunnel/bin/*.sh

Run setup:

bashCopycd ~/gpu-tunnel/bin
./01_local_setup.sh
