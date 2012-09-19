import pandas as pd
import numpy as np

from zipline.gens.tradegens import DataFrameSource
from zipline.utils.factory import create_trading_environment
from zipline.gens.transform import StatefulTransform
from zipline.lines import SimulatedTrading
from zipline.finance.slippage import FixedSlippage


class TradingAlgorithm(object):
    """
    Base class for trading algorithms. Inherit and overload handle_data(data).

    A new algorithm could look like this:
    ```
    class MyAlgo(TradingAlgorithm):
        def initialize(amount):
            self.amount = amount

        def handle_data(data):
            sid = self.sids[0]
            self.order(sid, amount)
    ```
    To then run this algorithm:

    >>> my_algo = MyAlgo(100, sids=[0])
    >>> stats = my_algo.run(data)

    """
    def __init__(self, sids, *args, **kwargs):
        """
        Initialize sids and other state variables.

        Calls user-defined initialize and forwarding *args and **kwargs.
        """
        self.sids = sids
        self.done = False
        self.order = None
        self.frame_count = 0
        self.portfolio = None

        self.registered_transforms = {}

        # call to user-defined initialize method
        self.initialize(*args, **kwargs)

    def _create_simulator(self, source):
        """
        Create trading environment, transforms and SimulatedTrading object.

        Gets called by self.run().
        """
        environment = create_trading_environment(start=source.data.index[0], end=source.data.index[-1])

        # Create transforms by wrapping them into StatefulTransforms
        transforms = []
        for namestring, trans_descr in self.registered_transforms.iteritems():
            sf = StatefulTransform(
                trans_descr['class'],
                *trans_descr['args'],
                **trans_descr['kwargs']
            )
            sf.namestring = namestring

            transforms.append(sf)

        # SimulatedTrading is the main class handling data streaming,
        # application of transforms and calling of the user algo.
        return SimulatedTrading(
            [source],
            transforms,
            self,
            environment,
            FixedSlippage()
        )

    def run(self, source):
        """
        Run the algorithm.

        :Arguments:
            data : zipline source or pandas.DataFrame
               pandas.DataFrame must have the following structure:
               * column names must consist of ints representing the different sids
               * index must be TimeStamps
               * array contents should be price

        :Returns:
            daily_stats : pandas.DataFrame
              Daily performance metrics such as returns, alpha etc.

        """
        if isinstance(source, pd.DataFrame):
            assert isinstance(source.index, pd.tseries.index.DatetimeIndex)
            source = DataFrameSource(source, sids=self.sids)

        # create transforms and zipline
        simulated_trading = self._create_simulator(source)

        # loop through simulated_trading, each iteration returns a
        # perf ndict
        perfs = list(simulated_trading)

        # convert perf ndict to pandas dataframe
        daily_stats = self._create_daily_stats(perfs)

        return daily_stats


    def _create_daily_stats(self, perfs):
        # create daily and cumulative stats dataframe
        daily_perfs = []
        cum_perfs = []
        for perf in perfs:
            if 'daily_perf' in perf:
                daily_perfs.append(perf['daily_perf'])
            else:
                cum_perfs.append(perf)

        daily_dts = [np.datetime64(perf['period_close'], utc=True) for perf in daily_perfs]
        daily_stats = pd.DataFrame(daily_perfs, index=daily_dts)

        return daily_stats

    def add_transform(self, transform_class, tag, *args, **kwargs):
        """Add a single-sid, sequential transform to the model.

        :Arguments:
            transform_class : class
                Which transform to use. E.g. mavg.
            tag : str
                How to name the transform. Can later be access via:
                data[sid].tag()

        Extra args and kwargs will be forwarded to the transform
        instantiation.

        """
        self.registered_transforms[tag] = {'class': transform_class,
                                           'args': args,
                                           'kwargs': kwargs}

    def set_portfolio(self, portfolio):
        self.portfolio = portfolio

    def set_order(self, order_callable):
        self.order = order_callable

    def get_sid_filter(self):
        return self.sids

    def set_logger(self, logger):
        self.logger = logger

    def initialize(self, *args, **kwargs):
        pass

    def set_slippage_override(self, slippage_callable):
        pass



