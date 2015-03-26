from kivy.uix.gridlayout import GridLayout
from kivy.clock import Clock
from kivy.uix.widget import WidgetException
from kivy.lang import Builder
Builder.load_file( 'libs/game/gamelayout.kv' )

from plyer import accelerometer, gyroscope

import utils, load_level
from physics_interface.physics_interface import PhysicsInterface
from success_screen.success_screen import SuccessScreen

LEVELS = 5

class GameLayout(GridLayout):
    ##### Initialization
    def __init__(self, swipebook, accel=None, gyro=None, compass=None, *args, **kwargs):
        super( GameLayout, self ).__init__( *args, **kwargs )

        # Function called when the player hits the menu button.
        self.go_to_menu = lambda : None

        # self.engine_running is True whenever self.Step() is scheduled, and false otherwise.
        self.engine_running = False

        # Toggle methods for play and pause that toggle custom textures. 
        # Changing button.background_normal and button.background_down might be easier but didn't seem to work.
        self.play_toggle  = utils.texture_toggle( 'Resources/play_normal.png', 'Resources/play_down.png' )
        self.pause_toggle = utils.texture_toggle( 'Resources/pause_normal.png', 'Resources/pause_down.png' )
        
        # Create the physics interface.
        self.physics_interface = PhysicsInterface( accelerometer, gyroscope )
        self.add_widget( self.physics_interface )

        self.need_to_remove_success_screen    = False
        self.in_success_screen                = False

        self.swipebook                        = swipebook

        # self.build_level() builds the level stored in the file named "levels/level{self.level_index}".
        self.level_index                      = 1
        
        # Keep track of which levels have been unlocked.
        # By default, only the first level is unlocked.
        self.levels_unlocked                  = [True] + [False for i in range( LEVELS - 1 )]
        self.level_scores                     = [None for i in range( LEVELS )]

        # Variable used to store the level_index of the level currently built.
        self.level_loaded                     = 0

        self.already_post_startup_initialized = False

        # Enable the device.
        accelerometer.enable()


    ##### Methods that have to do with levels.
    def unlock_next_level( self ):
        self.levels_unlocked[ self.level_index ] = True

    def get_unlocked_levels( self ):
        return self.levels_unlocked

    def set_level_score( self, x ):
        self.level_scores[ self.level_index - 1 ] = x

    def get_level_scores( self ):
        return self.level_scores


    ##### Post-startup initialization:
    # The widget tree is fully built and now coordinates are known.
    def post_startup_init( self, leaf=True ):
        if not self.already_post_startup_initialized:
            if leaf:
                self.already_post_startup_initialized = True

            self.success_screen = SuccessScreen( self, pos=self.pos, size=self.size )


    ##### Load the current level
    def build_level( self ):
        self.post_startup_init()

        # Only load the level when the level_index has changed.
        if self.level_loaded != self.level_index:
            load_level.remove_current_load_next( self.level_index, self.physics_interface )
            self.level_loaded = self.level_index


    QUICK = .2
    SHORT = 10
    # This method is best used in on_release, that way everything is known about the touch.
    def quick_and_short( self, touch ):
        "True if a touch is a quick tap with little movement."
        #            not self.touching_line and 
        return \
            touch.time_end - touch.time_start <= self.QUICK and utils.distance( touch.pos, touch.opos ) <= self.SHORT


    ##### Animation Step
    # This method is scheduled or unscheduled for playing or pausing, respectively.
    def Step( self, dt ):
        # Step the physics interface forward one unit of time dt.
        self.physics_interface.step( dt )

        # Respond to any notifications from self.physics_interface.
        for gameobject, notifications in self.physics_interface.get_notifications():
            for notice in notifications:

                if notice == 'Game Over':
                    self.reset()

                if notice == 'Level Complete':
                    try:
                        self.swipebook.add_widget_to_layer( self.success_screen, 'top' )
                        score = self.physics_interface.length_of_user_lines() 
                        self.set_level_score( score )
                        self.success_screen.set_score( score )
                        self.success_screen.add_screen()
                        self.in_success_screen = True
                    except WidgetException:
                        # Even when the success screen appears, the game is running.
                        # So there could be repeated 'Level Complete' notifications,
                        # resulting in WidgetException when trying to add SuccessScreen.
                        pass

                if notice == 'Remove':
                    try:
                        gameobject.remove()
                    except:
                        pass

        self.physics_interface.clear_notifications()


    ##### Callbacks and helpers for the top-of-the-screen buttons ('menu', 'play', 'pause') (which are defined in gamelayout.kv).
    def reset( self ):
        """Reset the gamelayout to its default state."""
        # Unschedule self.Step().
        Clock.unschedule( self.Step )
        self.engine_running = False

        # Reset pause and play to default states.
        self.play_toggle( self.ids.play_button, 'normal' )
        self.pause_toggle( self.ids.pause_button, 'down' )

        # Stop Level
        self.physics_interface.stop_level()

        if self.need_to_remove_success_screen:
            self.swipebook.remove_widget_from_layer( self.success_screen, 'top' )
            self.need_to_remove_success_screen = False

    def start_animation( self ):
        """Start the gamelayout into its running state."""
        # Set pause and play to playing states.
        self.play_toggle( self.ids.play_button, 'down' )
        self.pause_toggle( self.ids.pause_button, 'normal' )

        # Schedule self.Step()
        Clock.schedule_interval( self.Step, 1 / 60. )
        self.engine_running = True

        # Start Level
        self.physics_interface.start_level()

    # Texture loaders. 
    def get_menu_texture( self ):
        return utils.load_texture( 'Resources/menu.png' )
    def get_play_normal_texture( self ):
        return utils.load_texture( 'Resources/play_normal.png' )
    def get_pause_down_texture( self ):
        return utils.load_texture( 'Resources/pause_down.png' )

    def not_in_a_mode(self):
        return not any( [ b.state == 'down' for b in self.switches.values() ] ) 

    def menu_callback(self, button):
        if self.quick_and_short( button.last_touch ) and not self.in_success_screen:
            # Disable the devices.
            accelerometer.disable()

            self.go_to_menu()
            if self.engine_running:
                self.reset()

    def pause_callback(self, button):
        t = button.last_touch
        if self.quick_and_short( button.last_touch ) and not self.in_success_screen and \
           self.engine_running:
            self.reset()
        else:
            # Kivy toggles, even though a response is unwanted. Force 'down' state.
            button.state = 'down'

    def play_callback(self, button):
        t = button.last_touch
        if self.quick_and_short( button.last_touch ) and not self.in_success_screen and \
           not self.engine_running:
            self.start_animation()
        else:
            # Kivy toggles, even though a response is unwanted. Force 'down' state.
            button.state = 'down'
