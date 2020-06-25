import sys
import argparse
#import importlib 
import cmd
import getch
#import keyboard
#from pynput import keyboard


from machine_common_sense.mcs import MCS
from machine_common_sense.mcs_action import MCS_Action
from machine_common_sense.mcs_action_api_desc import MCS_Action_API_DESC
from machine_common_sense.mcs_action_keys import MCS_Action_Keys
from machine_common_sense.mcs_util import MCS_Util

# variables
commandList = []

# class to contain possible commands and keys
class command:
    def __init__(self, name, key, desc):
        self.name = name
        self.key = key
        self.desc = desc

class HumanInputShell(cmd.Cmd):

    prompt = '(command)->'

    controller = None
    previous_output = None
    config_data = None 

    def __init__(self, input_controller, input_previous_output, input_config_data):
        super(HumanInputShell,self).__init__()

        self.controller = input_controller
        self.previous_output = input_previous_output
        self.config_data = input_config_data

    def precmd(self, line):
        return line

    def postcmd(self, stopFlag, line) -> bool:
        #userCommand = line.split(',')
        #print('You entered command:')
        #print(*userCommand)
        print('===============================================================================')
        return stopFlag
        

    def default(self, line):

        if self.previous_output.action_list is not None and len(self.previous_output.action_list) < len(commandList):
            print('Only actions available during this step:')
            for action in self.previous_output.action_list:
                print('  ' + action)
        else:
            print('All actions are available during this step.')

        """
        if self.previous_output.action_list is not None and len(self.previous_output.action_list) == 1:
            print('Automatically selecting the only available action...')
            userInput = self.previous_output.action_list[1]
        else:
        """
        userInput = line.split(',')

        # Check for shortcut key, if attempted shortcut key, map and check valid key
        try:
            if len(userInput[0]) == 1:
                userInput[0] = MCS_Action[MCS_Action_Keys(userInput[0] ).name].value
        except:
            print("You entered an invalid shortcut key, please try again. (Type 'help' to display commands again)")
            print("You entered: " + userInput[0])
            return

        if userInput and userInput[0].lower() == 'exit':
            self.do_exit(line)
            return 
        if userInput and userInput[0].lower() == 'help':
            self.do_help(line)
            return
        if userInput and userInput[0].lower() == 'reset':
            self.do_reset(line)
            return 
            
        action, params = MCS_Util.input_to_action_and_params(','.join(userInput))

        if action is None:
            print("You entered an invalid command, please try again.  (Type 'help' to display commands again)")
            return

        if params is None:
            print("ERROR: Parameters should be separated by commas, and look like this example: rotation=45")
            return

        output = self.controller.step(action, **params)
        self.previous_output = output
    
    #def emptyline(self):
        #pass

    def help_print(self):
        print("Prints all commands that the user can use.")

    def help_exit(self):
        print("Exits out of the MCS Human Input program.")

    def help_reset(self):
        print("Resets the scene.")

    def help_shortcut_key_mode(self):
        print("Toggles on mode where the user can execute single key commands without hitting enter.")

    def do_exit(self, args) -> bool:
        print("Exiting Human Input Mode\n")
        return True

    def do_print(self, args):
        print_commands()

    def do_reset(self, args):
        self.previous_output = (self.controller).start_scene(self.config_data)

    def do_shortcut_key_mode(self, args):
        print("Entering shortcut mode...")
        print("Press key 'e' to exit\n")
        list_of_mcs_action_keys = [mcs_action_key.value for mcs_action_key in MCS_Action_Keys]

        while True:
            char = getch.getch()
            print('>',char)
            if char == 'e': # exit shortcut key mode
                break
            elif char in list_of_mcs_action_keys:
                self.default(char)
        



# Define all the possible human input commands
def build_commands():
    for action in MCS_Action:
        commandList.append(command(action.value, MCS_Action_Keys[action.name].value, MCS_Action_API_DESC[action.name].value))

# Display all the possible commands to the user along with key mappings
def print_commands():
    print(" ")
    print("--------------- Available Commands ---------------")
    print(" ")

    for commandListItem in commandList:
        print("- " + commandListItem.name + " (ShortcutKey=" + commandListItem.key + "): " + commandListItem.desc)

    print(" ")
    print("---------------- Example Commands ----------------")
    print(" ")
    print("MoveAhead")
    print("RotateLook, rotation=45, horizon=15")
    print(" ")
    print("----------------- Other Commands -----------------")
    print(" ")
    print("Enter 'print' to print the commands again.")
    print("Enter 'reset' to reset the scene.")
    print("Enter 'exit' to exit the program.")
    print(" ")
    print("------------------ End Commands ------------------")
    print(" ")

        
# Run scene loaded in the config data
def run_scene(controller, config_data):
    build_commands()
    print_commands()
    
    output = controller.start_scene(config_data)

    input_commands = HumanInputShell(controller, output, config_data)
    input_commands.cmdloop()

    sys.exit()
    

def main(argv): 
    
    parser = argparse.ArgumentParser(description='Run MCS')
    required_group = parser.add_argument_group(title='required arguments')

    required_group.add_argument('mcs_unity_build_file', help='Path to MCS unity build file')
    required_group.add_argument('mcs_config_json_file', help='MCS JSON scene configuration file to load')

    parser.add_argument('-d','--debug', default=True, help='True or False on whether to debug files [default=True]')
    parser.add_argument('-n','--noise', default=False, help='True or False on whether to enable noise in MCS [default=True]')
    parser.add_argument('-s','--seed', type=int, default=None, help='Seed(integer) for the random number generator [default=None]')
    args = parser.parse_args(argv[1:])
    
    if not isinstance(args.debug, bool):
        if args.debug.lower() != 'true' and args.debug.lower() != 'false':
            print('Debug files must be <True> or <False>')
            exit()
        else:
            if args.debug.lower() == 'false':
                args.debug = False
            else:
                args.debug = True


    if not isinstance(args.noise, bool):
        if args.noise.lower() != 'true' and args.noise.lower() != 'false':
            print('Enabling Noise must be <True> or <False>')
            exit()
        else:
            if args.noise.lower() == 'true':
                args.noise = True
            else:
                args.noise = False

    config_data, status = MCS.load_config_json_file(args.mcs_config_json_file)

    if status is not None:
        print(status)
        exit()

    debug = args.debug
    enable_noise = args.noise
    seed_val = args.seed
    
    #help(MCS)

    controller = MCS.create_controller(sys.argv[1], debug=debug, enable_noise=enable_noise, seed=seed_val)

    config_file_path = sys.argv[2]
    config_file_name = config_file_path[config_file_path.rfind('/')+1:]

    if 'name' not in config_data.keys():
        config_data['name'] = config_file_name[0:config_file_name.find('.')]

    run_scene(controller, config_data)

if __name__ == "__main__":
    main(sys.argv)


class HumanInputShell(cmd.Cmd):
    prompt = '>'
    controller = None
    previous_output = None
    config_data = None 

    def __init__(self, input_controller, input_previous_output, input_config_data):
        print("In constructor")

    def do_exit(self, args):
        print("In Exit")

    def do_help(self, args):
        print("In help")

    def do_reset(self, args):
        print("In reset")
