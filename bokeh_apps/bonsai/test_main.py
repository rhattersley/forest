# pylint: disable=missing-docstring, invalid-name
import unittest
import unittest.mock
import datetime as dt
import os
import yaml
import bokeh.plotting
import main
import numpy as np


class TestEnvironment(unittest.TestCase):
    def tearDown(self):
        for variable in ["FOREST_MODEL_DIR"]:
            if variable in os.environ:
                del os.environ[variable]

    def test_parse_env_given_forest_model_dir(self):
        os.environ["FOREST_MODEL_DIR"] = "/some/dir"
        result = main.parse_env().model_dir
        expect = "/some/dir"
        self.assertEqual(expect, result)

    def test_parse_env_default_forest_model_dir(self):
        result = main.parse_env().model_dir
        expect = None
        self.assertEqual(expect, result)


class TestConfig(unittest.TestCase):
    def setUp(self):
        self.path = "test-config.yaml"
        self.config = main.Config()

    def tearDown(self):
        if os.path.exists(self.path):
            os.remove(self.path)

    def test_merge_configs(self):
        dict_0 = dict(
            lat_range=[-5, 5],
            lon_range=[-180, 180])
        with open(self.path, "w") as stream:
            yaml.dump({"lon_range": [-10, 10]}, stream)
            dict_1 = main.Config.load_dict(self.path)
        merged = main.Config.merge(dict_0, dict_1)
        self.assertEqual(merged.lon_range, [-10, 10])
        self.assertEqual(merged.lat_range, [-5, 5])

    def test_load(self):
        with open(self.path, "w") as stream:
            yaml.dump({"lon_range": [-10, 10]}, stream)
        result = self.config.load(self.path).lon_range
        expect = [-10, 10]
        self.assertEqual(expect, result)

    def test_model_names(self):
        settings = {
            "models": [
                {"name": "A"},
                {"name": "B"}
            ]
        }
        with open(self.path, "w") as stream:
            yaml.dump(settings, stream)
        result = main.Config.load(self.path).model_names
        expect = ["A", "B"]
        self.assertEqual(expect, result)

    def test_model_dir(self):
        self.check_kwarg("model_dir", "/some/dir")

    def test_default_model_dir_returns_none(self):
        self.check_default("model_dir", None)

    def test_default_lon_range(self):
        self.check_default("lon_range", [-180, 180])

    def test_default_lat_range(self):
        self.check_default("lat_range", [-80, 80])

    def test_default_title(self):
        self.check_default("title", "Bonsai - miniature Forest")

    def test_default_models(self):
        self.check_default("models", [])

    def check_default(self, attr, expect):
        result = getattr(main.Config(), attr)
        self.assertEqual(expect, result)

    def check_kwarg(self, attr, expect):
        result = getattr(main.Config(**{attr: expect}), attr)
        self.assertEqual(expect, result)


class TestPubSub(unittest.TestCase):
    """Tiny publish/subscribe model to decouple views from controllers"""
    def setUp(self):
        self.state = main.State()
        self.view = unittest.mock.Mock()

    def test_register_notifies_views(self):
        self.state.register(self.view)
        self.state.on("model")("A")
        self.view.notify.assert_called_once_with({"model": "A"})

    def test_state_merges_streams(self):
        self.state.register(self.view)
        self.state.on("model")("A")
        self.state.on("date")("B")
        self.state.on("model")("B")
        calls = [
            unittest.mock.call({"model": "A"}),
            unittest.mock.call({"model": "A", "date": "B"}),
            unittest.mock.call({"model": "B", "date": "B"}),
        ]
        self.view.notify.assert_has_calls(calls)

    def test_register_can_listen_to_particular_changes(self):
        self.state.register(self.view, "model")
        self.state.on("model")("A")
        self.state.on("date")("B")
        self.state.on("model")("B")
        calls = [
            unittest.mock.call({"model": "A"}),
            unittest.mock.call({"model": "B", "date": "B"}),
        ]
        self.view.notify.assert_has_calls(calls)


class TestImage(unittest.TestCase):
    def test_constructor(self):
        document = bokeh.plotting.curdoc()
        figure = bokeh.plotting.figure()
        messenger = main.Messenger(figure)
        image = main.AsyncImage(
            document,
            figure,
            messenger)


class TestConvertUnits(unittest.TestCase):
    def test_convert_units(self):
        result = main.convert_units([1], "kg m-2 s-1", "kg m-2 hour-1")
        expect = np.array([3600.])
        np.testing.assert_array_almost_equal(expect, result)


class TestStretchY(unittest.TestCase):
    """Web Mercator projection introduces a y-axis stretching"""
    def test_stretch_y(self):
        values = [[0, 1, 2]]
        uneven_y = [0, 2, 3]
        transform = main.stretch_y(uneven_y)
        result = transform(values, axis=1)
        expect = [[0, 0.75, 2]]
        np.testing.assert_array_almost_equal(expect, result)


class TestFileSystem(unittest.TestCase):
    def setUp(self):
        self.file_system = main.FileSystem()

    def test_model_run_time_given_file_name(self):
        result = main.model_run_time("/some/file/takm4p4_20190305T1200Z.nc")
        expect = dt.datetime(2019, 3, 5, 12)
        self.assertEqual(expect, result)

    def test_model_run_time_given_different_time(self):
        result = main.model_run_time("/some/file/ga6_20180105T0000Z.nc")
        expect = dt.datetime(2018, 1, 5)
        self.assertEqual(expect, result)

    def test_find_file_by_date(self):
        paths = [
            "/some/file_20180101T0000Z.nc",
            "/some/file_20180101T1200Z.nc",
            "/some/file_20180102T1200Z.nc"]
        date = dt.datetime(2018, 1, 2, 12)
        result = self.file_system.find_file(paths, date)
        expect = "/some/file_20180102T1200Z.nc"
        self.assertEqual(expect, result)

    def test_full_pattern(self):
        file_system = main.FileSystem(models=[
            {"name": "A", "pattern": "a.nc"},
            {"name": "B", "pattern": "b.nc"}])
        result = file_system.full_pattern("A")
        expect = "a.nc"
        self.assertEqual(expect, result)


class TestTimeControls(unittest.TestCase):
    def test_time_controls(self):
        cb = unittest.mock.Mock()
        time_controls = main.TimeControls()
        time_controls.on_change(None, cb)
        time_controls.on_date(None, None, dt.date(2019, 1, 1))
        time_controls.on_time(None, None, 0)
        cb.assert_called_once_with(None, None, dt.datetime(2019, 1, 1, 0))

    def test_on_time(self):
        cb = unittest.mock.Mock()
        time_controls = main.TimeControls()
        time_controls.on_change("datetime", cb)
        time_controls.on_date(None, None, dt.date(2019, 1, 1))
        time_controls.on_time(None, None, 1)
        cb.assert_called_once_with(None, None, dt.datetime(2019, 1, 1, 12))