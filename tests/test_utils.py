"""Tests for functions and classes implemented in 'utils' module."""

import datetime
import pytest

from bayesian.utils import do_projection, fetch_file_from_github
from f8a_worker.enums import EcosystemBackend
from f8a_worker.models import Analysis, Ecosystem, Package, Version, WorkerResult
from urllib.request import urlopen

now = datetime.datetime.now()
later = now + datetime.timedelta(minutes=10)


@pytest.fixture
def analyses(app):
    """Prepare the known set of data used by tests."""
    e1 = Ecosystem(name='npm', backend=EcosystemBackend.npm)
    p1 = Package(ecosystem=e1, name='arrify')
    v1 = Version(package=p1, identifier='1.0.1')
    model1 = Analysis(version=v1, started_at=now, finished_at=later)
    app.rdb.session.add(model1)

    e2 = Ecosystem(name='pypi', backend=EcosystemBackend.pypi)
    p2 = Package(ecosystem=e2, name='flexmock')
    v2 = Version(package=p2, identifier='0.10.1')
    model2 = Analysis(version=v2, started_at=later, access_count=1)
    app.rdb.session.add(model2)
    app.rdb.session.commit()

    worker_results2 = {'a': 'b', 'c': 'd', 'e': 'f', 'g': 'h', 'i': 'j',
                       'digests': {'details':
                                   [{'artifact': True,
                                     'sha1': '6be7ae55bae2372c7be490321bbe5ead278bb51b'}]}}
    for w, tr in worker_results2.items():
        app.rdb.session.add(WorkerResult(analysis_id=model2.id, worker=w, task_result=tr))

    model3 = Analysis(version=v2, started_at=later, access_count=1,
                      audit={'audit': {'audit': 'audit', 'e': 'f', 'g': 'h'}, 'a': 'b', 'c': 'd'})
    app.rdb.session.add(model3)
    app.rdb.session.commit()
    worker_results3 = {'digests': {'details':
                                   [{'artifact': True,
                                     'sha1': '6be7ae55bae2372c7be490321bbe5ead278bb51b'}]}}
    for w, tr in worker_results3.items():
        app.rdb.session.add(WorkerResult(analysis_id=model3.id, worker=w, task_result=tr))
    app.rdb.session.commit()
    return (model1, model2, model3)


@pytest.mark.usefixtures('rdb')
class TestDoProjection(object):
    """Tests for the function 'do_projection' implemented in 'utils' module."""

    def test_empty_projection(self, analyses):
        """Test that no fields are returned for empty projection."""
        projection = []
        expected = {}
        result = do_projection(projection, analyses[0])
        assert expected == result

    def test_simple_projection(self, analyses):
        """Test simple projection of 2 simple arguments."""
        projection = ['ecosystem', 'package']
        # pypi has order 1
        expected = {'ecosystem': 'npm', 'package': 'arrify'}
        returned = do_projection(projection, analyses[0])
        assert expected == returned

    def test_none_projection(self, analyses):
        """Check that original model is returned if projection is None."""
        projection = None
        returned = do_projection(projection, analyses[0])
        expected = analyses[0].to_dict()
        assert expected == returned

    def test_nested_projection(self, analyses):
        """Test whether filtering of nested JSON returns just desired field."""
        projection = ['analyses.digests']
        expected = {'analyses': {'digests': {'details':
                                             [{'artifact': True, 'sha1':
                                               '6be7ae55bae2372c7be490321bbe5ead278bb51b'}]}}}
        result = do_projection(projection, analyses[1])
        assert expected == result

    def test_combined_projection(self, analyses):
        """Combining simple fields with nested fields."""
        projection = ['analyses.digests', 'analyses.a', 'package']
        expected = {'analyses': {'a': 'b', 'digests': {
            'details': [{'artifact': True, 'sha1': '6be7ae55bae2372c7be490321bbe5ead278bb51b'}]}},
                    'package': 'flexmock'}
        result = do_projection(projection, analyses[1])
        assert expected == result

    def test_three_level_fields(self, analyses):
        """Testing third level of nested JSON."""
        projection = ['analyses.digests.details', 'audit.audit.audit']
        expected = {'audit': {'audit': {'audit': 'audit'}},
                    'analyses':
                    {'digests': {'details':
                                 [{'artifact': True,
                                     'sha1': '6be7ae55bae2372c7be490321bbe5ead278bb51b'}]}}}
        result = do_projection(projection, analyses[2])
        assert expected == result


class TestFetchFileFromGithub:
    """Tests for the function 'fetch_file_from_github' implemented in 'utils' module."""

    __url = 'https://github.com/ravsa/testManifest'

    def test_github_url_exist_or_not(self):
        """Check for github repo exist or not."""
        assert urlopen(
            self.__url).code == 200, "Not able to access the url {}".format(self.__url)

    def test_repo_with_file_exist(self):
        """Check wheather file exist in github repo."""
        file_name = 'pom.xml'
        result = fetch_file_from_github(self.__url, file_name)
        assert not bool(
            {'filename', 'filepath', 'content'}.symmetric_difference(result[0].keys()))

    def test_repo_file_in_diff_branch(self):
        """Check for file exist in specific branch or not."""
        file_name = 'pom.xml'
        branch_name = 'dev-test-branch'
        result = fetch_file_from_github(
            self.__url, file_name, branch=branch_name)
        assert not bool(
            {'filename', 'filepath', 'content'}.symmetric_difference(result[0].keys()))
