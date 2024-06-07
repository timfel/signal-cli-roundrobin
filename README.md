# signal-cli-roundrobin
A simple script that uses signal-cli to send notifications round-robin to a group

1. Download the latest release of signal-cli: https://github.com/AsamK/signal-cli/releases/latest
2. Extract it next to `roundrobin.py`
3. If required, download a libsignal-client build from e.g. https://github.com/exquo/signal-libs-build/releases. (Other sources are explained here: https://github.com/AsamK/signal-cli/wiki/Provide-native-lib-for-libsignal)
    1. Add it to the signal-cli: https://github.com/AsamK/signal-cli/wiki/Provide-native-lib-for-libsignal#using-the-new-libsignal-client-lib-file
5. Use signal-cli "link" command to connect your Signal account with the script.
6. Modify roundrobin.py to set the correct group, telephone number, and timeout options.

The way I have it set up is just on a Raspberry Pi Zero that I have always running anyway.
I have added a crontab entry to just run the bot every day at 7, and it tells our daycare group who gets the lunch every day.
If people aren't there or the daycare is closed, they can respond with the commands to draw again or to skip the day and the bot obliges.
