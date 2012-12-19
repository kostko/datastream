import datetime, time, unittest

import mongoengine
import datastream

from datastream.backends import mongodb

class BasicTest(object):
    def _test_callback(self, metric_id, granularity, datapoint):
        self._callback_points.append((metric_id, granularity, datapoint))

    def test_basic(self):
        query_tags = [
            {'name': 'foobar'},
        ]
        tags = [
            'more',
            {'andmore': 'bar'},
        ]
        metric_id = self.datastream.ensure_metric(query_tags, tags, self.value_downsamplers, datastream.Granularity.Seconds)

        metric = datastream.Metric(self.datastream.get_tags(metric_id))
        self.assertEqual(metric.id, metric_id)
        self.assertItemsEqual(metric.value_downsamplers, self.value_downsamplers)
        self.assertItemsEqual(metric.time_downsamplers, self.time_downsamplers)
        self.assertEqual(metric.highest_granularity, datastream.Granularity.Seconds)
        self.assertItemsEqual(metric.tags, query_tags + tags)

        # Test metric tag manipulation
        rm_tags = self.datastream.get_tags(metric_id)
        self.datastream.remove_tag(metric_id, 'more')
        new_tags = self.datastream.get_tags(metric_id)
        rm_tags.remove('more')
        self.assertItemsEqual(new_tags, rm_tags)

        self.datastream.clear_tags(metric_id)
        metric = datastream.Metric(self.datastream.get_tags(metric_id))
        self.assertItemsEqual(metric.tags, [])

        self.datastream.update_tags(metric_id, query_tags + tags)
        metric = datastream.Metric(self.datastream.get_tags(metric_id))
        self.assertItemsEqual(metric.tags, query_tags + tags)

        # Should not do anything
        self.datastream.downsample_metrics()

        data = self.datastream.get_data(metric_id, datastream.Granularity.Seconds, datetime.datetime.utcfromtimestamp(0), datetime.datetime.utcfromtimestamp(time.time()))
        self.assertItemsEqual(data, [])

        data = self.datastream.get_data(metric_id, datastream.Granularity.Minutes, datetime.datetime.utcfromtimestamp(0), datetime.datetime.utcfromtimestamp(time.time()))
        self.assertItemsEqual(data, [])

        # Callback should not have been fired
        self.assertItemsEqual(self._callback_points, [])

        self.datastream.append(metric_id, 42)
        self.assertRaises(datastream.exceptions.InvalidValue, lambda: self.datastream.append(metric_id, 42, datetime.datetime.min))

        data = self.datastream.get_data(metric_id, datastream.Granularity.Seconds, datetime.datetime.utcfromtimestamp(0), datetime.datetime.utcfromtimestamp(time.time()))
        self.assertEqual(len(data), 1)

        self.assertEqual(len(self._callback_points), 1)
        cb_metric_id, cb_granularity, cb_datapoint = self._callback_points[0]
        self.assertEqual(cb_metric_id, metric_id)
        self.assertEqual(cb_granularity, datastream.Granularity.Seconds)
        self.assertItemsEqual(cb_datapoint, data[0])

        data = self.datastream.get_data(metric_id, datastream.Granularity.Minutes, datetime.datetime.utcfromtimestamp(0))
        self.assertItemsEqual(data, [])

        # Artificially increase backend time for a minute so that downsample will do something for minute granularity
        self.datastream.backend._time_offset += datetime.timedelta(minutes=1)

        self.datastream.downsample_metrics()

        data = self.datastream.get_data(metric_id, datastream.Granularity.Seconds, datetime.datetime.utcfromtimestamp(0), datetime.datetime.utcfromtimestamp(time.time()) + self.datastream.backend._time_offset)
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]['v'], 42)

        data = self.datastream.get_data(metric_id, datastream.Granularity.Seconds, datetime.datetime.utcfromtimestamp(0))
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]['v'], 42)

        self.assertEqual(len(self._callback_points), 3)
        cb_metric_id, cb_granularity, cb_datapoint = self._callback_points[1]
        self.assertEqual(cb_metric_id, metric_id)
        self.assertEqual(cb_granularity, datastream.Granularity.Seconds10)
        cb_metric_id, cb_granularity, cb_datapoint = self._callback_points[2]
        self.assertEqual(cb_metric_id, metric_id)
        self.assertEqual(cb_granularity, datastream.Granularity.Minutes)

        value_downsamplers_keys = [datastream.VALUE_DOWNSAMPLERS[d] for d in self.value_downsamplers]
        time_downsamplers_keys = [datastream.TIME_DOWNSAMPLERS[d] for d in self.time_downsamplers]

        data = self.datastream.get_data(metric_id, datastream.Granularity.Minutes, datetime.datetime.utcfromtimestamp(0), datetime.datetime.utcfromtimestamp(time.time()) + self.datastream.backend._time_offset)
        self.assertEqual(len(data), 1)
        self.assertItemsEqual(data[0]['v'].keys(), value_downsamplers_keys)
        self.assertItemsEqual(data[0]['t'].keys(), time_downsamplers_keys)
        self.assertItemsEqual(data[0], cb_datapoint)

        data = self.datastream.get_data(metric_id, datastream.Granularity.Minutes, datetime.datetime.utcfromtimestamp(0))
        self.assertEqual(len(data), 1)
        self.assertItemsEqual(data[0]['v'].keys(), value_downsamplers_keys)
        self.assertItemsEqual(data[0]['t'].keys(), time_downsamplers_keys)
        self.assertTrue(datastream.VALUE_DOWNSAMPLERS['count'] in data[0]['v'].keys())

        data = self.datastream.get_data(metric_id, datastream.Granularity.Minutes, datetime.datetime.utcfromtimestamp(0), value_downsamplers=('count',))
        self.assertEqual(len(data), 1)
        self.assertItemsEqual(data[0]['v'].keys(), (datastream.VALUE_DOWNSAMPLERS['count'],))
        self.assertEqual(data[0]['v'][datastream.VALUE_DOWNSAMPLERS['count']], 1)

    def test_data(self):
        query_tags = [
            {'name': 'foodata'},
        ]
        tags = []

        metric_id = self.datastream.ensure_metric(query_tags, tags, self.value_downsamplers, datastream.Granularity.Seconds)
        metric = datastream.Metric(self.datastream.get_tags(metric_id))

        ts = datetime.datetime(2000, 1, 1, 12, 0, 0)
        for i in range(1200):
            self.datastream.append(metric_id, i, ts)
            ts += datetime.timedelta(0, 1)





class MongoDBBasicTest(BasicTest, unittest.TestCase):
    database_name = 'test_database'

    def setUp(self):
        self.datastream = datastream.Datastream(mongodb.Backend(self.database_name), self._test_callback)
        self.value_downsamplers = self.datastream.backend.value_downsamplers
        self.time_downsamplers = self.datastream.backend.time_downsamplers
        self._callback_points = []

    def tearDown(self):
        db = mongoengine.connection.get_db(mongodb.DATABASE_ALIAS)
        for collection in db.collection_names():
            if collection == 'system.indexes':
                continue
            db.drop_collection(collection)
