import unittest
import unittest.mock
import bokeh.layouts
import forest.control
import forest.actions
import os
import datetime as dt
import netCDF4


class TestFileSystem(unittest.TestCase):
    def setUp(self):
        self.controller = forest.control.FileSystem()

    def test_render(self):
        self.controller.render({})
        self.assertIsInstance(self.controller.layout, bokeh.layouts.Column)

    def test_render_given_state(self):
        state = {
            'file_names': ["hello.nc", "goodbye.nc"]
        }
        self.controller.render(state)
        result = self.controller.dropdown.menu
        expect = [("hello.nc", "hello.nc"), ("goodbye.nc", "goodbye.nc")]
        self.assertEqual(expect, result)

    def test_render_given_state_without_file_names(self):
        state = {}
        self.controller.render(state)
        result = self.controller.dropdown.menu
        expect = []
        self.assertEqual(expect, result)

    def test_render_given_file_name(self):
        state = {
            'file': "hello.nc"
        }
        self.controller.render(state)
        result = self.controller.dropdown.label
        expect = "hello.nc"
        self.assertEqual(expect, result)

    def test_on_file_emits_action(self):
        attr, old, new = None, None, "file.nc"
        listener = unittest.mock.Mock()
        self.controller.subscribe(listener)
        self.controller.on_file(attr, old, new)
        action = ("set file", "file.nc")
        listener.assert_called_once_with(action)


class TestStore(unittest.TestCase):
    def setUp(self):
        self.store = forest.control.Store(forest.control.reducer)

    def test_default_state(self):
        result = self.store.state
        expect = {}
        self.assertEqual(expect, result)

    def test_dispatch_given_action_updates_state(self):
        action = forest.actions.set_file("file.nc")
        self.store.dispatch(action)
        result = self.store.state
        expect = {
            "file": "file.nc"
        }
        self.assertEqual(expect, result)

    def test_store_state_is_observable(self):
        action = forest.actions.set_file("file.nc")
        listener = unittest.mock.Mock()
        self.store.subscribe(listener)
        self.store.dispatch(action)
        expect = {"file": "file.nc"}
        listener.assert_called_once_with(expect)


class TestReducer(unittest.TestCase):
    def test_reducer(self):
        result = forest.control.reducer({}, ("set file", "file.nc"))
        expect = {
            "file": "file.nc"
        }
        self.assertEqual(expect, result)

    def test_reducer_given_set_file_names_action(self):
        files = ["a.nc", "b.nc"]
        action = forest.actions.set_file_names(files)
        result = forest.control.reducer({}, action)
        expect = {
            "file_names": files
        }
        self.assertEqual(expect, result)

    def test_reducer_given_set_variable(self):
        action = forest.actions.set_variable("air_temperature")
        result = forest.control.reducer({}, action)
        expect = {
            "variable": "air_temperature"
        }
        self.assertEqual(expect, result)


class TestMiddlewares(unittest.TestCase):
    def test_middleware_log_actions(self):
        action = ("Hello", "World!")
        log = forest.control.ActionLog()
        store = forest.control.Store(forest.control.reducer, middlewares=[log])
        store.dispatch(action)
        result = log.actions
        expect = [action]
        self.assertEqual(expect, result)

    def test_middleware_sql_database(self):
        db = forest.control.Database()
        store = forest.control.Store(forest.control.reducer,
                                     middlewares=[db])
        action = forest.actions.set_file("file.nc")
        store.dispatch(action)
        result = store.state
        expect = {
            "file": "file.nc",
            "variables": ["mslp"]
        }
        self.assertEqual(expect, result)


class TestNetCDFMiddleware(unittest.TestCase):
    def setUp(self):
        self.path = "test-file.nc"
        middleware = forest.control.NetCDF()
        self.store = forest.control.Store(forest.control.reducer,
                                     middlewares=[middleware])

    def tearDown(self):
        if os.path.exists(self.path):
            os.remove(self.path)

    def test_middleware_netcdf(self):
        with netCDF4.Dataset(self.path, "w") as dataset:
            dataset.createDimension("x", 1)
            dataset.createVariable("air_temperature", "f", ("x"))
            dataset.createVariable("relative_humidity", "f", ("x"))

        self.store.dispatch(forest.actions.set_file(self.path))

        result = self.store.state
        expect = {
            "file": self.path,
            "variables": ["air_temperature", "relative_humidity"]
        }
        self.assertEqual(expect, result)

    def test_given_file_and_variable_triggers_set_valid_times(self):
        units = "hours since 1970-01-01 00:00:00 utc"
        with netCDF4.Dataset(self.path, "w") as dataset:
            dataset.createDimension("time_0", 1)
            var = dataset.createVariable("time_0", "f", ("time_0",))
            var.units = units
            var[:] = netCDF4.date2num([dt.datetime(2019, 1, 1)], units=units)
            dataset.createVariable("air_temperature", "f", ("time_0",))

        self.store.dispatch(forest.actions.set_file(self.path))
        self.store.dispatch(forest.actions.set_variable("air_temperature"))

        result = self.store.state["valid_times"]
        expect = [dt.datetime(2019, 1, 1)]
        self.assertEqual(expect, result)