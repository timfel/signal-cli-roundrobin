#!/usr/bin/env python3
import os
import glob
import subprocess
import json
import random
import time
import re

# BEGIN: CONFIGURATION
PHONENUMBER = "+49123456789"
DESIRED_GROUP = "Test group"
MINUTES_TO_LISTEN_FOR_ANSWERS = 60 * 4
TOKEN_GOES_TO = "Heute geht das Essen an @mention. -- Euer Essensverteiler-Bot"
NO_ONE_TO_DRAW = "Heute scheint niemand da zu sein. -- Euer Essensverteiler-Bot"
DRAW_AGAIN_CMD = "lieber bot: neu ziehen"
DRAW_AGAIN_ANSWER = "Ok, habe @mention wieder in den Pool genommen und ziehe neu. -- Euer Essensverteiler-Bot"
NOT_TODAY_CMD = "lieber bot: heute nicht"
NOT_TODAY_ANSWER = "Ok, heute nicht, habe @mention wieder in den Pool genommen. -- Euer Essensverteiler-Bot"
IGNORE_MEMBER_AND_DRAW_AGAIN_CMD = "lieber bot: ignorieren und neu ziehen"
IGNORE_MEMBER_AND_DRAW_AGAIN_ANSWER = "Ok, werde @mention ab sofort ignorieren und ziehe neu. -- Euer Essensverteiler-Bot"
# END: CONFIGURATION


EXE = os.path.join(os.path.dirname(__file__), "signal-cli*", "bin", "signal-cli")
if os.name == "nt":
    EXE += ".bat"
EXE = glob.glob(EXE)
EXE.sort()
EXE = EXE[-1]
print("Using", EXE)


def cmd(*args):
    print(">>>", repr(args))
    out = subprocess.check_output([EXE, "-u", PHONENUMBER, "-o", "json", *args], encoding="utf-8")
    print("<<<", out)
    if out and args[0] == "receive":
        lines = out.split("\n")
        return [json.loads(line.strip()) for line in lines if line.strip()]
    try:
        return json.loads(out)
    except:
        return None


class Bot:
    def __init__(self,
        groupname: str,
        msg_token: str,
        msg_no_one: str,
        cmd_draw_again: str,
        msg_draw_again: str,
        cmd_not_today: str,
        msg_not_today: str,
        cmd_ignore: str,
        msg_ignore: str,
        minutes_to_listen: int,
    ) -> None:
        self.groupname = groupname
        self.msg_token = msg_token
        self.msg_no_one = msg_no_one
        self.cmd_draw_again = cmd_draw_again
        self.msg_draw_again = msg_draw_again
        self.cmd_not_today = cmd_not_today
        self.msg_not_today = msg_not_today
        self.cmd_ignore = cmd_ignore
        self.msg_ignore = msg_ignore
        self.minutes_to_listen = minutes_to_listen

        self.db = os.path.join(os.path.dirname(__file__), f"{self.groupname}.json")
        if not os.path.exists(self.db):
            with open(self.db, "w", encoding="utf-8") as f:
                json.dump({"ignoredMembers": [], "servedMembers": []}, f)

        cmd("receive", "-t", "1", "--ignore-attachments", "--ignore-stories")
        groups = cmd("listGroups", "-d")
        interesting_groups: list[dict] = [g for g in groups if g["name"] == self.groupname]
        if not interesting_groups:
            print(f"""
            Group {self.groupname} wasn't found, are you sure the name is right?
            Maybe try sending a message there and re-running this script, since
            that can trigger a Signal sync event to get group details for this
            bot.
            """)
            return -1
        interesting_group = interesting_groups[0]
        self.group_members: set[str] = set(m["uuid"] for m in interesting_group["members"])
        self.group_id: str = interesting_group["id"]

        with open(self.db, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.ignored_members: set[str] = set(data["ignoredMembers"])
        self.served_members: set[str] = set(data["servedMembers"])
        self.currently_unavailable_members: set[str] = set()

    def choose_next(self) -> str:
        pending_members = list(self.group_members - self.served_members - self.currently_unavailable_members - self.ignored_members)
        if not pending_members:
            pending_members = list(self.group_members - self.currently_unavailable_members - self.ignored_members)
            self.served_members.clear()
        if not pending_members:
            return None
        random.shuffle(pending_members)
        next_member = pending_members[0]
        self.served_members.add(0)
        return next_member

    def run(self):
        try:
            self._send_and_receive()
        finally:
            with open(self.db, "w", encoding="utf-8") as f:
                json.dump(
                    {
                        "ignoredMembers": list(self.ignored_members),
                        "servedMembers": list(self.served_members),
                    },
                    f,
                )

    def _send_and_receive(self):
        must_draw = True
        bot_response: str = ""
        end_time = time.time() + self.minutes_to_listen * 60

        def mention_user_in_msg(user, msg):
            start = msg.index("@mention")
            length = len("@mention")
            return f"{start}:{length}:{user}"

        def match_cmd(msg, cmd):
            return re.sub(r"[^\w]", "", msg) == re.sub(r"[^\w]", "", cmd)

        while time.time() < end_time:
            if bot_response:
                args = ["send", "-g", self.group_id, "--notify-self", "-m", bot_response]
                if "@mention" in bot_response and next_member:
                    args += ["--mention", mention_user_in_msg(next_member, bot_response)]
                bot_response = ""
                cmd(*args)
            if must_draw:
                next_member = self.choose_next()
                must_draw = False
                if next_member is None: # nobody available today
                    cmd("send", "-g", self.group_id, "--notify-self", "-m", self.msg_no_one)
                    break
                cmd("send", "-g", self.group_id, "--notify-self", "-m", self.msg_token, "--mention", mention_user_in_msg(next_member, self.msg_token))
            messages = cmd("receive", "-t", "1", "--ignore-attachments", "--ignore-stories") or []
            for msg in messages:
                if "envelope" in msg:
                    msg = msg["envelope"]
                if "syncMessage" in msg:
                    msg = msg["syncMessage"]
                if "sentMessage" in msg:
                    msg = msg["sentMessage"]
                if "dataMessage" in msg:
                    msg = msg["dataMessage"]
                if "message" in msg and "groupInfo" in msg and msg["groupInfo"]["groupId"] == self.group_id:
                    message: str = msg["message"].lower().strip()
                    if match_cmd(message, self.cmd_not_today):
                        if next_member in self.served_members:
                            self.served_members.remove(next_member)
                        end_time = 0 # breaks out of outer loop
                        break # break out of message handling
                    elif match_cmd(message, self.cmd_draw_again):
                        self.currently_unavailable_members.add(next_member)
                        if next_member in self.served_members:
                            self.served_members.remove(next_member)
                        bot_response = self.msg_draw_again
                        must_draw = True
                    elif match_cmd(message, self.cmd_ignore):
                        self.ignored_members.add(next_member)
                        if next_member in self.served_members:
                            self.served_members.remove(next_member)
                        bot_response = self.msg_ignore
                        must_draw = True
            time.sleep(60)


if __name__ == "__main__":
    bot = Bot(
        groupname=DESIRED_GROUP,
        msg_token=TOKEN_GOES_TO,
        msg_no_one=NO_ONE_TO_DRAW,
        cmd_draw_again=DRAW_AGAIN_CMD,
        msg_draw_again=DRAW_AGAIN_ANSWER,
        cmd_not_today=NOT_TODAY_CMD,
        msg_not_today=NOT_TODAY_ANSWER,
        cmd_ignore=IGNORE_MEMBER_AND_DRAW_AGAIN_CMD,
        msg_ignore=IGNORE_MEMBER_AND_DRAW_AGAIN_ANSWER,
        minutes_to_listen=MINUTES_TO_LISTEN_FOR_ANSWERS,
    )
    bot.run()
