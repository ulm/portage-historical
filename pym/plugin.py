#!/usr/bin/python

"""
Plug-In Framework - version 1.3
Copyright 2003 - Alain Penders  (alain@rexorient.com or alain@gentoo.org)

This framework enables an application to easily load plugins.  Each plugin
can register functions that are called when certain events occurs in the
application.


This library is free software; you can redistribute it and/or
modify it under the terms of the GNU Lesser General Public
License as published by the Free Software Foundation; either
version 2.1 of the License, or (at your option) any later version.

This library is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
Lesser General Public License for more details.

You should have received a copy of the GNU Lesser General Public
License along with this library; if not, write to the Free Software
Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
"""

import string,sys,types,os.path


#-----------------------------------------------------------------------------

# Determine our version, and setup True/False accordingly.

myversion = sys.version
myversion = string.split(myversion, ' ')[0]
myversion = string.split(myversion, '.')
myversion = (int(myversion[0])*10000)+(int(myversion[1])*100)+int(myversion[2])

if (myversion < 20201):
	True = 1
	False = 0


#-----------------------------------------------------------------------------


class Plugin:
	"""Plugin handler class.
	
	This class provides methods to load and unload plugins, as well as methods that can
	be used by said plugins to register callbacks.
	
	
	1. Loading classes
	
	In order to load a class or a plugin (which is also a class), you need to specify its
	name.  There are two ways to specify names, each of which uses a different way to find
	the class.  Please keep on reading, and make sure you understand how and where classes
	are looked for!
	
	Lets start off with some definitions.  The "initial module" is the file that python
	started with.  For example, if you type "python helloworld.py", helloworld is the
	initial module.  This file is treated special by the search algorithm as python does
	not see it as an imported module.  The name of the initial module is the name of the
	file that python started with.  If python started with the "-c" option, the initial
	module does not have a name.

	Modules can be identified using single (e.g. "os") or multi-part (e.g. "os.path")
	names.  If it's a multi-part name, we refer to the last part as the "module", and the
	previous parts are the "module path".  For example, "my.precious.ring" is the module
	name, "my.precious" is the module path, and "ring" is the module.

	It's possible to specify the class/plugin using either the class name or the module name
	*and* the class name.  For example, the class "dblink" in module "portage.storage" can be
	identified as "dblink" or as "portage.storage.dblink".
	
	When specifying the class by class name only:
	  - We look if the initial module contains the class, if not
	  - we look if any of the imported modules contain the class, if not
	  - we throw a PluginException.
	  
	  Since no module name is specified, no attempt will be made to import a module to
	  resolve the class name.
	  
	  If multiple of the imported modules contain a matching class, which class will be
	  returned is unpredictable (dangerous!).

	When specifying the class by module name and class name:
	  - If the module matches the "initial module" name:
	     - We look if the initial module contains the class, if not
	     - We throw a PluginException
	  - We look whether the specified module name was imported.  If not, we import it.
	  - We look if this module contains the class, if not we throw a PluginException.
	  
	  Note that only the module (not the module path) is matched against the initial
	  module name, so "os.merge" will match "merge" for that check.

	For any class to match, it *must* have loadable defined in its global data:

	   class myloadable:
	      loadable = 1
	      
	      def __init__(self):
	         print "hello world"

	The above is a valid loadable class.  Note that the type or value of loadable doesn't
	matter, so changing loadable to "False" or 0 will not prevent it from being loaded.


	2. Working with plugins

	This framework provides three methods for handling plugins:
	  - load_plugin(name)
	  - unload_plugin(name)
	  - unload_all_plugins()

	Each plugin is a class.  The name is used to load that class, and must follow the rules
	for loading a class as described above.

	To unload a plugin, the name given must be identical to the name provided to load it.

	Upon loading a plugin, an instance of the plugin is created.  This causes the class`
	__init__() method to be called, from which the plugin can do initialization work, such as
	setting up callbacks (see below).
	
	Upon unloading a plugin, its unload() method is called.  This method can take care of
	removing callbacks, etc.  If the plugin will never be unloaded, the unload() method can be
	omitted.  However, if it is omitted and the application tries to unload it anyway, a
	PluginException will be thrown.  (See the unload_plugin() and unload_all_plugins()
	documentation for more details.)
	
	Both the __init__() and unload() methods get a handle to the plugin class that's loading/
	unloading them passed in.  This handle is needed to setup or remove callbacks.

	For example:
	
	   import plugin

	   class myplugin:
	      loadable = 1

	      def __init__(self, hdlr):
	         print "Initializing plug-in ..."
	         hdlr.add_callback("print", 100, self.print)

	      def unload(self, hdlr):
	         print "Unloading plug-in ..."
	         hdlr.remove_callback("print", 100, self.print)

	      def print(self, args):
	         print "Hello World!"

	   plugins = plugin.Plugin(pathlist)
	   plugins.load_plugin("myplugin")
	   ...
	   plugins.inload_plugin("myplugin")


	3. Using callbacks

	While loading and unloading plugins is cool, for it to be useful the plugin needs to be able
	to interact with the application.  One way of making that happen is using the callback
	system provided as part of this module.
	
	The concept of callbacks is that the plugin "registers" for events it is interested in by
	saying "if this event occurs, call me".  The method that handles that call is the
	"callback".
	
	We use named callbacks, allowing the plugin to install a callback before the application
	has defined it, or even install a callback that gets called by another plugin --
	dependent on whether or not that plugin is loaded.

	Three methods are provided to work with callbacks, the first two mainly for plugins, the
	latter mainly for the application:
	  - add_callback(name, priority, function)
	  - remove_callback(name, priority, function)
	  - call(name, args)

	"name" identifies the event, and should be a string.
	"priority" gives the priority for this callback.  (See next paragraphs.)
	"function" is the callback function or method to be called when a call() is made on this event.
	"args" is a single argument that will be passed on to the callback functions/methods.
	
	More than one plugin can register for an event.  Sometimes it doesn't matter which plugin is
	informed first of an event, in which case all plugins can add their callbacks with the same
	priority (100).  In this case the plugin that got added first will be called first.

	When the priority does matter, the plugins should set the priority parameter to sensible
	values.  The lower its value, the higher the priority.  Plugins should never set it lower than
	20, or higher than 200, leaving values outside of that range for use by the application.

	Using prioritized callbacks also allows for a low priority callback to be installed that deals
	with the event if none of the previous callbacks did.

	Normally, every callback registered to an event will be called in order of priority.  The
	return value of the last callback is what is returned from the call() method.  The return
	values of all previous (higher priority) callbacks are lost.  This can be changed using the
	CallbackException.  If a callback wants to return its value, and stop the lower priority
	callbacks from being called, it can raise a CallbackException with its return value as the
	exception value.

	Below is an example on how to use plugins for sorting emails to mailboxes.  A callback is used
	to determine the mailbox name, and a default low-priority callback is installed to handle
	mails that aren't handled by any of the plugins.

	   import plugin

	   class subject_filter:
	      loadable = 1

	      def __init__(self, hdlr):
	         hdlr.add_callback("mailbox", 100, self.sort_mailbox)

	      def unload(self, hdlr):
	         hdlr.remove_callback("mailbox", 100, self.sort_mailbox)

	      def sort_mailbox(self, email):
	         #
		 # If the subject contains "URGENT", place in the "urgent" mailbox
		 #
	         if (email.subject.contains("URGENT")):
	            raise CallbackException("urgent")
	         #
		 # If the subject contains "Adv", place in the "spam" mailbox
		 #
	         if (email.subject.contains("Adv")):
	            raise CallbackException("spam")
		
	   class from_filter:
	      loadable = 1

	      def __init__(self, hdlr):
	         hdlr.add_callback("mailbox", 80, self.sort_mailbox)

	      def unload(self, hdlr):
	         hdlr.remove_callback("mailbox", 80, self.sort_mailbox)

	      def sort_mailbox(self, email):
	         #
		 # If From: contains "alain@gentoo.org", place in the "alain" mailbox
		 #
	         if (email.from.contains("alain@gentoo.org")):
	            raise CallbackException("alain")
	         #
		 # If From: contains "drobbins@gentoo.org", place in the "drobbins" mailbox
		 #
	         if (email.from.contains("drobbins@gentoo.org")):
	            raise CallbackException("drobbins")

	   #
	   # The default callback always places the mail in the Inbox
	   #
	   def default_mailbox(email):
	   	return "Inbox"

	   #
	   # Initialize the plugin framework, and pass it the paths to look for plugins.
	   #
	   plugins = plugin.Plugin(pathlist)

	   # Load our plugins
	   plugins.load_plugin("subject_filter")
	   plugins.load_plugin("from_filter")
	   
	   # Add the default mailbox handler -- it priority is always lower than any of the
	   # plugins.
	   plugins.add_callback("mailbox", 250, default_mailbox)

	   ...

	   def new_mail(email):
	      ...
	      mailbox = plugins.call("mailbox", email)
	      place_in_mailbox(mailbox, email)
	      ...

	   ...

	Note: Use multiples of 10 for the priorities.  When adding a new callback and a previous
	callback exists with the same priority, the priority is increased by 1 until no callback
	exists with that priority.  So adding callbacks respectively at priority 10, 11, 10 would
	result in the last callback to be added with priority 12 -- after the 2nd callback instead
	of before it.


	4. Using load_module
	
	The module this method refers to is not a module in the python sense (which can be imported),
	but rather a class that provides loadable functionality for an application.
	
	The main difference between load_module(name) and load_class(name) is that the first returns
	a class instance, and the latter returns the class.  load_module() is useful for
	applications that want to load a named class, and make calls to it.
	
	For example, the cursingcow installer uses one class for each step of the installer.  These
	classes are linked together using a state-machine.  An easy implementation of a state-
	machine proving Back, Next, and Abort functionality in each step is shown in the code below:

	   import plugin
	   
	   steps = [ "welcome", "cc_disk.partitions", "cc_disk.format", "cc_core.packages",
	             "cc_core.users", "cc_support.printers", None ]
           
	   STEP_NEXT     =  1
	   STEP_ABORT    =  0
	   STEP_PREVIOUS = -1
	   
	   plugins = plugin.Plugin(paths)
	   i = 0
	   
	   while (steps[i] != None):
	      module = plugins.load_module(steps[i])
	      result = module.run()
	      if (result == STEP_PREVIOUS):
	         i -= 1
	      elif (result == STEP_ABORT):
	         sys.exit(1)
	      else:
	         # must be STEP_NEXT
	         i += 1

	This example assumed that every module-class implements a run() method that carries out the
	modules actions.
	"""

	#------------------------------------------------------------------------------

	def __init__(self, paths, debug_callback=None):
		"""Constructor.
		
		<paths> can be a single path or a list of paths in which we'll look for plug-in
		modules.
		
		If "debug_callback" is provided, it must be a debug callback as defined in the
		set_debug_callback() method.
		"""
		self.paths = paths
		self.plugins={}
		self.hooks={}
		self.ourname=None
		self.loader_globals=None
		self.debug_callback = debug_callback
		self.debug("Plugin Framework initialized")


	def set_debug_callback(self, debug_callback):
		"""Install a debug callback.
		
		This can be a function or a method which takes 1 parameter, the debug message.
		If you log the message together with other messages, you should make sure you
		can tell they came from the plugin framework.
		"""
		self.debug_callback = debug_callback
		self.debug("New debug_callback set")


	def debug(self, message):
		"""-*-(Private)-*-  Print a debug message if a debug callback is installed."""
		if (self.debug_callback != None):
			self.debug_callback(message)


	def load_class(self, name):
		"""Load a class.
		
		This method returns the class if it manages to load it, or throws a
		PluginException if it doesn't.  No class instance is created by this call.

		"name" identifies the class to be loaded, using the format
		[[<modulepath>.]*<module>.]<classname>

		See "Class loading" above for more information about the name parameter and
		how classes are found.

		A module is never loaded twice by this method.  If the module has been loaded
		before by the plugin class, by a generic "import" statement, or because it's
		the main program module, it will be found and reused.

		Note: if a module is already loaded, it's possible that a class that's in it is
		not found.  This happens when the code that starts the class loading occurs
		above the class definition.  Python will start the class loading without having
		parsed the rest of the module, and hence won't know that the class exists in it!
		To prevent this, always place your "main" program at the end of the module!
		"""

		self.debug("Loading class '"+name+"' ...")

		# Some initialization code -- find our name and the globals for the python file
		# this app started with.
		if not self.ourname:

			# Get the start module name
			c = sys.argv[0]
			if (c == "-c"):
				self.ourname = "-c"
			else:
				self.ourname = os.path.basename(c)
				if (string.find(self.ourname, ".") != -1):
					self.ourname = string.split(self.ourname, '.')[0]
				if (len(self.ourname) == 0):
					self.ourname = "-c"

			# This tricky piece of code gets the globals for the start module.  It
			# does this by grabbing a Frame Object from an exception, and tracing
			# back to the root frame.  (See the python traceback module for other
			# code that uses this.)
			try:
				raise ZeroDivisionError
			except ZeroDivisionError:
				frame = sys.exc_info()[2].tb_frame
			while (frame.f_back != None):
				frame = frame.f_back
			self.loader_globals = frame.f_globals

		sp = string.split(name,'.')
		l  = len(sp)
		daclass = None

		if (l == 1):
			try:
				daclass = self.loader_globals[name]
				if type(daclass) is not types.ClassType:
					daclass = None
				else:
					try:
						daclass.__dict__["loadable"]
					except:
						daclass = None
			except:
				pass
			if daclass:
				self.debug("Found '"+name+"' in initial module!")
				return daclass

			for modname in sys.modules:
				try:
					mod = sys.modules[modname]
					daclass = mod.__dict__[name]
					if type(daclass) is not types.ClassType:
						daclass = None
					else:
						try:
							daclass.__dict__["loadable"]
						except:
							daclass = None
				except:
					continue
				if daclass:
					self.debug("Found '"+name+"' in module "+modname)
					return daclass

			self.debug("Unable to find class '"+name+"' in currently loaded modules!")
			raise PluginException("Unable to find class",name,"in currently loaded modules!")
		else:
			# Get the module, lastmodule, and classname.
			module = string.join(sp[:-1], '.')
			lastmodule = sp[-2]
			classname = sp[-1]

			# If the module name is the same are our initial module name, we
			# grab the class from the initial module.  If it's not there we
			# fail.  Even if the user did actually specify a different module,
			# we still won't try to find that module as we risk reloading the
			# initial module which would cause an endless loop.

			if ((self.ourname != "-c") and (self.ourname == lastmodule)):
				# The module the user wants may be us, search the globals!

				try:
					daclass = self.loader_globals[classname]
					if type(daclass) is not types.ClassType:
						self.debug("'"+classname+"' exists in initial module ("+lastmodule+"), but is not a class!")
						raise PluginException("'"+classname+"' exists in initial module ("+lastmodule+"), but is not a class!")
					else:
						try:
							daclass.__dict__["loadable"]
						except:
							self.debug("Class '"+classname+"' in initial module ("+lastmodule+") is not 'loadable'!")
							raise PluginException("Class '"+classname+"' in initial module ("+lastmodule+") is not 'loadable'!")
				except KeyError:
					self.debug("The initial module ("+lastmodule+") does not contain class '"+classname+"'!")
					raise PluginException("The initial module ("+lastmodule+") does not contain class '"+classname+"'!")
				if daclass:
					self.debug("Found '"+name+"' in initial module ("+lastmodule+")!")
					return daclass

			# Get the module, import it if it doesn't exist yet.
			try:
				mod = sys.modules[module]
			except:
				try:
					self.debug("Importing module '"+module+"' ...")
					mod = __import__(module, globals(), locals(), self.paths)
				except:
					self.debug("Unable to find or load module '"+module+"'!")
					raise PluginException("Unable to find or load module '"+module+"'!")

			# Find the top-level component
			components = string.split(module, '.')
			for comp in components[1:]:
				mod = getattr(mod, comp)

			# Get a handle on our class
			try:
				daclass = mod.__dict__[classname]
			except:
				self.debug("Module '"+module+"' does not have a class called '"+classname+"'!")
				raise PluginException("Module '"+module+"' does not have a class called '"+classname+"'!")

			if type(daclass) is not types.ClassType:
				self.debug("'"+classname+"' exists in '"+module+"', but is not a class!")
				raise PluginException("'"+classname+"' exists in '"+module+"', but is not a class!")

			try:
				daclass.__dict__["loadable"]
			except:
				self.debug("Class '"+classname+"' in module '"+module+"' is not 'loadable'!")
				raise PluginException("Class '"+classname+"' in module '"+module+"' is not 'loadable'!")

			self.debug("Found '"+name+"' in module '"+module+"'!")
			return daclass


	def load_module(self, name):
		"""Load a module.

		This method loads a class, creates an instance of it, and returns that instance.

		"name" identifies the class to be loaded, using the format
		[[<modulepath>.]*<module>.]<classname>

		See "Class loading" above for more information about the name parameter and
		how classes are found.
		"""

		# Load the class
		daclass = self.load_class(name)

		# Initialize it
		instance = daclass()

		self.debug("Loaded module '"+name+"'.")

		return instance


	def load_plugin(self, name):
		"""Load a plug-in.
		
		This method loads and initializes a plug-in class.  Initialization is done by
		creating an instance, which results in a call to its constructor method.  If the
		plugin is loaded and initialized successfully, this method returns nothing.  If
		an error occurs, an PluginException will be thrown.

		"name" identifies the class to be loaded, using the format
		[[<modulepath>.]*<module>.]<classname>

		See "Class loading" above for more information about the name parameter and
		how classes are found.

		Example of a plug-on class:
		
		   class myplugin:
		      loadable = 1

		      def __init__(self, hdlr):
		         print "Initializing plug-in ..."
		         hdlr.add_callback("print", 10, self.print)

		      def unload(self, hdlr):
		         print "Unloading plug-in ..."
		         hdlr.remove_callback("print", 10, self.print)

		      def print(self, args):
		         print "Hello World!"

		The plug-ins __init__() (called on loading) and unload() methods get a reference to
		the plugin class instance that's loading/unloading them passed in.  This allows them
		to install callbacks on that plugin framework.

		The unload() method is only needed if the plug-in can be unloaded.  If a plug-in will
		never be unloaded, the method can be omitted.  If the method is omitted and an unload
		occurs anyway, the unload will throw a PluginException.
		"""

		daclass = self.load_class(name)

		# Initialize the class
		instance = daclass(self)

		# Keep track of it
		self.plugins[name] = instance

		self.debug("Loaded plugin '"+name+"'.")


	def unload_plugin(self, name):
		"""Unload a plugin.
		
		This method unloads a plugin, and returns nothing on success.  On failure it will throw
		a PluginException.  Reasons for failure include the plugin never being loaded or not
		supporting unload.

		"name" identifies the class to be loaded, using the format
		[[<modulepath>.]*<module>.]<classname>

		See "Class loading" above for more information about the name parameter and
		how classes are found.

		Note: if the plug-in does not support unloading, a PluginException will be thrown, and
		it will *NOT* be removed from the loaded plug-in list.  To empty the list, use
		unload_all_plugins() instead.
		"""
		try:
			instance = self.plugins[name]
			instance.unload(self)
			del self.plugins[name]
			self.debug("Unloaded plugin '"+name+"' ...")
		except KeyError:
			self.debug("Can't unload plugin '"+name+"', it wasn't loaded!")
			raise PluginException("Can't unload plugin '"+name+"', it wasn't loaded!")
		except AttributeError:
			self.debug("Plugin '"+name+"' doesn't support unloading!  It must have an unload() method!")
			raise PluginException("Plugin '"+name+"' doesn't support unloading!  It must have an unload() method!")


	def unload_all_plugins(self):
		"""Unload all loaded plugins.
		
		This method will traverse the list of loaded plugins, and unload each one of them.  If a
		plugin doesn't support unloading, the failure count will be increased, and it will still
		be removed from the loaded plugins list.  (So at the end of this method, the loaded plugins
		list will always be empty *unless* the unload method of a plugin throws an exception which
		isn't caught by this method -- any exception other than AttributeError.)

		After all plugins have been handled, this method will throw an exception if the failure
		count is not zero.
		"""
		failures = 0
		for name in self.plugins.keys():
			instance = self.plugins[name]
			try:
				instance.unload(self)
			except AttributeError:
				failures = failures + 1
			del self.plugins[name]
		if failures:
			self.debug("Unload all plugins: "+failures+" plugins did not support unloading!")
			raise PluginException(failures+" plugins did not support unloading!")
		else:
			self.debug("All plugins unloaded.")


	def add_callback(self, name, priority, function):
		"""Add a named callback.

		To support plug-ins, it must be possible for the plug-in to hook into the existing
		application.  This is done through named callbacks.  When something happens in the
		application that a plug-in may want to know about or respond to, the application
		makes a call, providing the name of the event.  Plug-ins can register callback
		functions with the name of the event that will trigger them.

		<name> Identifies the event to add this callback to.

		<priority> Since multiple callbacks can be registered for one event, it may be
		important to execute the callbacks in the right order.  The priority allows a
		callback to be moved forward or backward in the call list.  The lower the value,
		the higher the priority.
		
		<function> The callback function to run when this event occurs.
		
		Note 1: Never use a priority below 10 or above 200!  Values outside of those
		boundaries are reserved for the application.
		
		Note 2: If you don't know what priority to use, 100 is a safe bet.

		Note 3: Every registered callback function will be called, unless one of them
		throws an exception.  See the call() method for information on how to use the
		special CallbackException.
		"""
		hk = self.get_hook(name, False)
		try:
			hk.add(priority, function)
			self.debug("Added callback for event '"+name+"' with priority '"+str(priority)+"'")
		except:
			self.debug("Adding callback for event '"+name+"' with priority '"+str(priority)+"' failed: "+str(sys.exc_info()[1]))
			raise PluginException(sys.exc_info()[1])

	def remove_callback(self, name, priority, function):
		"""Remove a named callback.
		
		All three parameters have to be the same as those used for add_callback, or this
		method will fail with a PluginException.
		"""
		hk = self.get_hook(name, True)
		if (hk == None):
			self.debug("Can't remove a callback ("+name+") that hasn't been added!")
			raise PluginException("Can't remove a callback ("+name+") that hasn't been added!")
		try:
			hk.remove(priority, function)
			self.debug("Removed callback for event '"+name+"' with priority '"+str(priority)+"'")
		except:
			self.debug("Removing callback for event '"+name+"' with priority '"+str(priority)+"' failed: "+str(sys.exc_info()[1]))
			raise PluginException(sys.exc_info()[1])


	def get_hook(self, name, optional):
		"""-*-Private-*- Get a named hook.  If optional is true, this returns None if the
		hook hasn't been created yet.  If it's false, the hook will be created if needed.
		"""
		try:
			hk = self.hooks[name]
		except:
			if not optional:
				hk = Hook()
				self.hooks[name] = hk
			else:
				hk = None
		return hk


	def call(self, name, args):
		"""Call the callback functions associated with a named event.
		
		<name> Identifies the event that occured.
		
		<args> Is passed on to the callback functions as their argument.
		
		Every callback function added to this event name will be called in order of priority.
		The result returned by the last function (lowest priority) is returned from this call.
		
		The only way to avoid all functions from being called is throwing an exception.  A
		special exception exists to help with this, the CallbackException.  The value of this
		exception should be set to the return value of your callback, and will be returned by
		this method.  Any other exception will be passed through and will have to be dealt
		with in your code.
		"""
		hk = self.get_hook(name, True)
		if not hk:
			return None
		return hk.call(args)


#-----------------------------------------------------------------------------


class Hook:
	"""Hook class.
	
	This class is used by the Plugin class to keep track of all the callback
	functions associated with one event.  This system allows plug-ins to "hook"
	into the event.
	"""

	def __init__(self):
		"""Constructor."""
		self.calls= {}
		self.keys = None


	def add(self, priority, function):
		"""Add a callback function.
		
		See plugin.add_callback() for documentation on the parameters and usage.
		"""
		self.keys = None
		try:
			key=priority
			while(self.calls[key]):
				if (self.calls[key] == function):
					raise HookException("Don't add a callback twice!")
				key = key + 1
		except:
			self.calls[key] = function


	def remove(self, priority, function):
		"""Remove a callback function.
		
		See plugin.remove_callback() for documentation on the parameters and usage.
		"""
		self.keys = None
		try:
			key=priority
			while(self.calls[key]):
				if (self.calls[key] == function):
					del self.calls[key]
					return
				key = key + 1
		except:
			raise HookException("Can't remove a callback that wasn't added!")
			self.calls[key] = function


	def call(self, args):
		"""Call the callback functions.
		
		See plugin.call() for documentation on the parameters and usage.
		"""
		if (self.keys == None):
			self.keys = self.calls.keys()
			self.keys.sort()
		result = None
		try:
			for key in self.keys:
				result = self.calls[key](args)
		except CallbackException:
			result = sys.exc_value
		return result


#-----------------------------------------------------------------------------


class PluginException(Exception):
	"""Exception thrown when an error occurs inside the Plugin class."""
	def info(self):
		print "An error occured in the usage of the Plugin class!"


#-----------------------------------------------------------------------------


class HookException(Exception):
	"""Exception thrown when an error occurs inside the Hook class."""
	def info(self):
		print "An error occured in the usage of the Hook class!"


#-----------------------------------------------------------------------------


class CallbackException(Exception):
	"""Exception that can be thrown by a callback function to avoid execution of
	lower priority callback functions.  The value of this exception should be
	set, and will be returned by the call() method."""
	def info(self):
		print "A function associated with this event terminated the callback calling."


#-----------------------------------------------------------------------------
