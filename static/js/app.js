/**
 * SeminarFinal_v2.1 - Client JavaScript
 */

class StockSimulator {
    constructor() {
        this.socket = null;
        this.djiChart = null;
        this.sp500Chart = null;
        this.djiLabels = [];
        this.djiData = [];
        this.sp500Labels = [];
        this.sp500Data = [];
        this.currentPrices = {};
        this.previousPrices = {};
        this.portfolio = { cash: 1000, holdings: {} };
        this.currentTicker = null;
        this.tradeType = null;
        this.headlineCache = {};
        this.activeMode = 'historical';

        this.init();
    }

    init() {
        this.connectSocket();
        this.initCharts();
        this.bindEvents();
    }

    connectSocket() {
        this.socket = io({
            reconnection: true,
            reconnectionDelay: 1000,
            reconnectionDelayMax: 5000,
            reconnectionAttempts: 5
        });

        this.socket.on('connect', () => {
            console.log('Connected to server');
            this.socket.emit('join_room', {
                room_code: window.roomCode,
                username: window.username
            });
        });

        this.socket.on('joined_room', (data) => {
            this.updateAdminControls(data.is_admin);
        });

        this.socket.on('game_state_update', (data) => {
            this.updateGameState(data);
        });

        this.socket.on('leaderboard_update', (data) => {
            this.updateLeaderboard(data.leaderboard);
        });

        this.socket.on('market_event', (data) => {
            this.handleMarketEvent(data);
        });

        this.socket.on('market_panic', (data) => {
            this.handleMarketPanic(data);
        });

        this.socket.on('new_headline', (data) => {
            this.updateHeadlineTicker(data);
        });

        this.socket.on('info', (data) => {
            if (data && data.message) {
                this.showToast(data.message, 'info');
            }
        });

        this.socket.on('insider_rumor', (data) => {
            this.updateRumorTicker(data);
        });

        this.socket.on('insider_status_updated', (data) => {
            this.handleInsiderStatusUpdate(data);
        });

        this.socket.on('sec_penalty', (data) => {
            this.handleSECPenalty(data);
        });

        this.socket.on('mode_toggled', (data) => {
            this.handleModeToggled(data);
        });
    }

    initCharts() {
        const djiCtx = document.getElementById('dji-chart').getContext('2d');
        const sp500Ctx = document.getElementById('sp500-chart').getContext('2d');

        const commonOptions = {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false },
                tooltip: {
                    mode: 'index',
                    intersect: false,
                    backgroundColor: '#161b22',
                    borderColor: '#30363d',
                    borderWidth: 1,
                    titleFont: { family: 'Inter' },
                    bodyFont: { family: 'JetBrains Mono' }
                }
            },
            scales: {
                x: {
                    display: true,
                    grid: { color: 'rgba(48, 54, 61, 0.5)' },
                    ticks: {
                        color: '#8b949e',
                        maxTicksLimit: 8,
                        font: { family: 'JetBrains Mono', size: 10 }
                    }
                },
                y: {
                    display: true,
                    grid: { color: 'rgba(48, 54, 61, 0.5)' },
                    ticks: {
                        color: '#8b949e',
                        font: { family: 'JetBrains Mono', size: 10 },
                        callback: (value) => '$' + value.toLocaleString()
                    }
                }
            },
            interaction: {
                mode: 'nearest',
                axis: 'x',
                intersect: false
            }
        };

        this.djiChart = new Chart(djiCtx, {
            type: 'line',
            data: {
                labels: this.djiLabels,
                datasets: [{
                    label: 'DJI',
                    data: this.djiData,
                    borderColor: '#f59e0b',
                    backgroundColor: 'rgba(245, 158, 11, 0.12)',
                    borderWidth: 2,
                    fill: true,
                    tension: 0.35,
                    pointRadius: 0,
                    pointHoverRadius: 4
                }]
            },
            options: commonOptions
        });

        this.sp500Chart = new Chart(sp500Ctx, {
            type: 'line',
            data: {
                labels: this.sp500Labels,
                datasets: [{
                    label: 'S&P 500',
                    data: this.sp500Data,
                    borderColor: '#38bdf8',
                    backgroundColor: 'rgba(56, 189, 248, 0.12)',
                    borderWidth: 2,
                    fill: true,
                    tension: 0.35,
                    pointRadius: 0,
                    pointHoverRadius: 4
                }]
            },
            options: commonOptions
        });
    }

    bindEvents() {
        document.querySelectorAll('.btn-buy').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const ticker = e.target.dataset.ticker;
                this.openTradeModal(ticker, 'buy');
            });
        });

        document.querySelectorAll('.btn-sell').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const ticker = e.target.dataset.ticker;
                this.openTradeModal(ticker, 'sell');
            });
        });

        document.getElementById('modal-close').addEventListener('click', () => this.closeModal());
        document.getElementById('modal-cancel').addEventListener('click', () => this.closeModal());
        document.getElementById('modal-confirm').addEventListener('click', () => this.executeTrade());
        document.getElementById('dollar-input').addEventListener('input', () => this.updateTradeTotal());

        if (window.isAdmin) {
            document.getElementById('play-pause-btn').addEventListener('click', () => this.socket.emit('admin_toggle_play'));
            document.getElementById('set-date-btn').addEventListener('click', () => {
                const date = document.getElementById('date-picker').value;
                this.socket.emit('admin_set_date', { date });
            });
            document.getElementById('reset-btn').addEventListener('click', () => {
                if (confirm('Reset the game for all players?')) {
                    this.socket.emit('admin_reset');
                }
            });

            const modeToggle = document.getElementById('mode-toggle');
            if (modeToggle) {
                modeToggle.checked = window.isPracticeMode || false;
                modeToggle.addEventListener('change', () => {
                    this.socket.emit('admin_toggle_mode');
                });
            }

            const insiderUsernameInput = document.getElementById('insider-username');
            const setInsiderButton = document.getElementById('set-insider-btn');
            const revokeInsiderButton = document.getElementById('revoke-insider-btn');

            if (setInsiderButton && insiderUsernameInput) {
                setInsiderButton.addEventListener('click', () => {
                    const target = insiderUsernameInput.value.trim();
                    if (!target) {
                        this.showToast('Enter a username to grant insider access.', 'error');
                        return;
                    }
                    this.socket.emit('admin_set_insider', { username: target, is_insider: true });
                });
            }

            if (revokeInsiderButton && insiderUsernameInput) {
                revokeInsiderButton.addEventListener('click', () => {
                    const target = insiderUsernameInput.value.trim();
                    if (!target) {
                        this.showToast('Enter a username to revoke insider access.', 'error');
                        return;
                    }
                    this.socket.emit('admin_set_insider', { username: target, is_insider: false });
                });
            }
        }

        document.getElementById('trade-modal').addEventListener('click', (e) => {
            if (e.target.id === 'trade-modal') {
                this.closeModal();
            }
        });
    }

    updateGameState(data) {
        document.getElementById('current-date').textContent = data.current_date;
        this.updateHeadlineForDate(data.current_date);

        const statusIndicator = document.getElementById('status-indicator');
        const statusText = document.getElementById('status-text');

        if (data.game_state === 'playing') {
            statusIndicator.classList.add('playing');
            statusText.textContent = 'Playing';
            if (window.isAdmin) {
                document.getElementById('play-pause-btn').innerHTML = '<span class="btn-icon">⏸</span> Pause';
            }
        } else {
            statusIndicator.classList.remove('playing');
            statusText.textContent = 'Paused';
            if (window.isAdmin) {
                document.getElementById('play-pause-btn').innerHTML = '<span class="btn-icon">▶</span> Play';
            }
        }

        this.updatePrices(data.prices);
        this.updateCharts(data.current_date, data.prices);
        this.updateAvailableTickers(data.available_tickers || []);

        if (data.panic_mode) {
            this.setPanicVisuals(true);
        } else {
            this.setPanicVisuals(false);
        }

        this.requestPortfolioUpdate();
    }

    updatePrices(prices) {
        this.previousPrices = { ...this.currentPrices };
        this.currentPrices = prices;

        window.tickers.forEach(ticker => {
            const priceEl = document.getElementById(`price-${ticker}`);
            const changeEl = document.getElementById(`change-${ticker}`);
            const statusEl = document.getElementById(`status-${ticker}`);
            const buyBtn = document.querySelector(`.btn-buy[data-ticker="${ticker}"]`);
            const sellBtn = document.querySelector(`.btn-sell[data-ticker="${ticker}"]`);

            const price = prices[ticker];

            if (price === undefined || price === null) {
                priceEl.textContent = 'N/A';
                changeEl.textContent = '';
                statusEl.textContent = 'Not yet IPO\'d';
                statusEl.className = 'stock-status unavailable';
                buyBtn.disabled = true;
                sellBtn.disabled = true;
            } else {
                priceEl.textContent = this.formatCurrency(price);

                const prevPrice = this.previousPrices[ticker];
                if (prevPrice && prevPrice !== price) {
                    const change = ((price - prevPrice) / prevPrice) * 100;
                    changeEl.textContent = (change >= 0 ? '+' : '') + change.toFixed(2) + '%';
                    changeEl.className = 'price-change ' + (change >= 0 ? 'positive' : 'negative');

                    const card = document.querySelector(`.stock-card[data-ticker="${ticker}"]`);
                    card.classList.add(change >= 0 ? 'price-flash-up' : 'price-flash-down');
                    setTimeout(() => {
                        card.classList.remove('price-flash-up', 'price-flash-down');
                    }, 500);
                }

                statusEl.textContent = '';
                statusEl.className = 'stock-status';
                buyBtn.disabled = false;
                sellBtn.disabled = false;
            }
        });
    }

    updateCharts(date, prices) {
        if (!date) {
            return;
        }

        this.addChartPoint(this.djiChart, this.djiLabels, this.djiData, date, prices['^DJI']);
        this.addChartPoint(this.sp500Chart, this.sp500Labels, this.sp500Data, date, prices['^GSPC']);

        this.updateIndexValues(prices);
    }

    addChartPoint(chart, labels, data, date, value) {
        if (value === undefined || value === null) {
            return;
        }

        const lastLabel = labels[labels.length - 1];
        if (lastLabel === date) {
            data[data.length - 1] = value;
        } else {
            labels.push(date);
            data.push(value);
        }

        if (labels.length > 100) {
            labels.splice(0, labels.length - 100);
            data.splice(0, data.length - 100);
        }

        chart.data.labels = labels;
        chart.data.datasets[0].data = data;
        chart.update('none');
    }

    updateIndexValues(prices) {
        const djiValue = prices['^DJI'];
        const sp500Value = prices['^GSPC'];
        document.getElementById('dji-value').textContent = djiValue ? this.formatCurrency(djiValue) : '--';
        document.getElementById('sp500-value').textContent = sp500Value ? this.formatCurrency(sp500Value) : '--';
    }

    async requestPortfolioUpdate() {
        try {
            const response = await fetch(`/api/player/${window.roomCode}/${window.username}`);
            const data = await response.json();
            this.updatePortfolio(data);
        } catch (error) {
            console.error('Error fetching portfolio:', error);
        }
    }

    updatePortfolio(data) {
        this.portfolio = { cash: data.cash, holdings: data.holdings };
        document.getElementById('cash-balance').textContent = this.formatCurrency(data.cash);

        let holdingsValue = 0;
        Object.entries(data.holdings).forEach(([ticker, shares]) => {
            const price = this.currentPrices[ticker] || 0;
            holdingsValue += shares * price;
        });

        document.getElementById('holdings-value').textContent = this.formatCurrency(holdingsValue);
        document.getElementById('net-worth').textContent = this.formatCurrency(data.net_worth);

        const holdingsList = document.getElementById('holdings-list');
        if (!Object.keys(data.holdings).length) {
            holdingsList.innerHTML = '<p class="empty-message">No holdings yet</p>';
            return;
        }

        let html = '';
        Object.entries(data.holdings).forEach(([ticker, shares]) => {
            const price = this.currentPrices[ticker] || 0;
            const value = shares * price;
            html += `
                <div class="holding-item">
                    <span class="holding-ticker">${ticker}</span>
                    <span class="holding-shares">${shares.toFixed(2)} shares</span>
                    <span class="holding-value">${this.formatCurrency(value)}</span>
                </div>
            `;
        });
        holdingsList.innerHTML = html;
    }

    updateLeaderboard(leaderboard) {
        const list = document.getElementById('leaderboard-list');
        let html = '';

        leaderboard.forEach((entry, index) => {
            const isCurrentUser = entry.username === window.username;
            const rankClass = index === 0 ? 'gold' : index === 1 ? 'silver' : index === 2 ? 'bronze' : 'other';
            html += `
                <div class="leaderboard-item">
                    <span class="leaderboard-rank ${rankClass}">${index + 1}</span>
                    <div class="leaderboard-info">
                        <span class="leaderboard-name ${isCurrentUser ? 'you' : ''}">${entry.username}${isCurrentUser ? ' (You)' : ''}</span>
                    </div>
                    <span class="leaderboard-worth">${this.formatCurrency(entry.net_worth)}</span>
                </div>
            `;
        });

        list.innerHTML = html;
    }

    openTradeModal(ticker, type) {
        this.currentTicker = ticker;
        this.tradeType = type;

        const price = this.currentPrices[ticker];
        if (!price) {
            this.showToast('Stock not available for trading', 'error');
            return;
        }

        document.getElementById('modal-title').textContent = type === 'buy' ? `Buy ${ticker}` : `Sell ${ticker}`;
        document.getElementById('modal-ticker').textContent = ticker;
        document.getElementById('modal-price').textContent = this.formatCurrency(price);

        const dollarInput = document.getElementById('dollar-input');
        const inputLabel = document.getElementById('trade-input-label');
        const totalLabel = document.getElementById('trade-total-label');

        if (type === 'buy') {
            inputLabel.textContent = 'Dollar Amount';
            totalLabel.textContent = 'Estimated Shares:';
            dollarInput.value = Math.min(100, this.portfolio.cash || 1000);
            dollarInput.max = this.portfolio.cash || 0;
            dollarInput.min = 1;
            dollarInput.step = 0.01;
        } else {
            inputLabel.textContent = 'Number of Shares';
            totalLabel.textContent = 'Total Value:';
            const ownedShares = this.portfolio.holdings[ticker] || 0;
            dollarInput.value = ownedShares.toFixed(2);
            dollarInput.max = ownedShares;
            dollarInput.min = 0.01;
            dollarInput.step = 0.01;
        }

        this.updateTradeTotal();
        const confirmBtn = document.getElementById('modal-confirm');
        confirmBtn.className = 'btn btn-confirm ' + type;
        confirmBtn.textContent = type === 'buy' ? 'Buy' : 'Sell';
        document.getElementById('trade-modal').classList.add('active');
    }

    closeModal() {
        document.getElementById('trade-modal').classList.remove('active');
        this.currentTicker = null;
        this.tradeType = null;
    }

    updateTradeTotal() {
        const amount = parseFloat(document.getElementById('dollar-input').value) || 0;
        const price = this.currentPrices[this.currentTicker];
        let displayValue = '0.00';

        if (this.tradeType === 'buy') {
            const shares = price ? amount / price : 0;
            displayValue = shares > 0 ? shares.toFixed(8) : '0.00';
        } else {
            const total = price ? amount * price : 0;
            displayValue = price ? this.formatCurrency(total) : '0.00';
        }

        document.getElementById('trade-total').textContent = displayValue;
    }

    executeTrade() {
        const amount = parseFloat(document.getElementById('dollar-input').value);

        if (!amount || amount <= 0) {
            this.showToast(this.tradeType === 'buy' ? 'Please enter a valid dollar amount' : 'Please enter a valid share amount', 'error');
            return;
        }

        if (this.tradeType === 'buy') {
            this.socket.emit('buy_stock', {
                ticker: this.currentTicker,
                amount
            });
        } else {
            this.socket.emit('sell_stock', {
                ticker: this.currentTicker,
                shares: amount
            });
        }

        this.closeModal();
    }

    showToast(message, type = 'info') {
        const toast = document.createElement('div');
        toast.className = `toast ${type}`;
        toast.textContent = message;
        document.body.appendChild(toast);

        setTimeout(() => {
            toast.classList.add('visible');
        }, 20);

        setTimeout(() => {
            toast.classList.remove('visible');
            setTimeout(() => toast.remove(), 300);
        }, 3200);
    }

    handleSECPenalty(data) {
        this.showToast(data.message || 'SEC enforcement penalty applied.', 'error');
        if (data && typeof data.cash_remaining === 'number') {
            document.getElementById('cash-balance').textContent = this.formatCurrency(data.cash_remaining);
            this.requestPortfolioUpdate();
        }
    }

    updateRumorTicker(data) {
        const wrapper = document.getElementById('rumor-wrap');
        const rumorText = document.getElementById('rumor-text');
        if (!wrapper || !rumorText) return;

        if (window.isInsider && data && data.headline) {
            wrapper.classList.remove('hidden');
            rumorText.textContent = data.headline;
            return;
        }

        wrapper.classList.add('hidden');
    }

    handleInsiderStatusUpdate(data) {
        if (data && typeof data.is_insider !== 'undefined') {
            window.isInsider = data.is_insider;
            const headerRight = document.querySelector('.header-right');
            const existingBadge = document.querySelector('.insider-badge');

            if (window.isInsider) {
                if (!existingBadge && headerRight) {
                    const badge = document.createElement('span');
                    badge.className = 'insider-badge';
                    badge.textContent = 'Insider';
                    headerRight.appendChild(badge);
                }
            } else if (existingBadge) {
                existingBadge.remove();
            }
        }

        if (data && data.message) {
            this.showToast(data.message, 'info');
        }
    }

    handleMarketPanic(data) {
        this.setPanicVisuals(true);
        if (data && data.message) {
            this.showToast(data.message, 'error');
        }
    }

    setPanicVisuals(enabled) {
        document.querySelectorAll('.chart-container, .ticker-wrap').forEach(el => {
            if (!el) return;
            el.classList.toggle('panic-mode', enabled);
        });
    }

    handleMarketEvent(data) {
        if (data && data.message) {
            this.showToast(data.message, 'info');
        }
    }

    updateAvailableTickers(tickers) {
        window.tickers.forEach(ticker => {
            const buyBtn = document.querySelector(`.btn-buy[data-ticker="${ticker}"]`);
            const sellBtn = document.querySelector(`.btn-sell[data-ticker="${ticker}"]`);
            const isAvailable = tickers.includes(ticker);
            if (buyBtn) {
                buyBtn.disabled = !isAvailable;
                buyBtn.style.opacity = isAvailable ? '1' : '0.5';
            }
            if (sellBtn) {
                sellBtn.disabled = !isAvailable;
                sellBtn.style.opacity = isAvailable ? '1' : '0.5';
            }
        });
    }

    updateHeadlineForDate(dateString) {
        if (!dateString || dateString.length < 4) return;
        const year = dateString.slice(0, 4);
        const headlineEl = document.getElementById('headline-text');
        const yearLabel = document.getElementById('news-year-label');

        yearLabel.textContent = `Year: ${year}`;

        if (this.headlineCache[year]) {
            headlineEl.textContent = this.headlineCache[year].headline;
            return;
        }

        headlineEl.textContent = 'Loading headline...';
        fetch(`/api/headline/${year}`)
            .then((response) => response.json())
            .then((payload) => {
                this.headlineCache[year] = payload;
                headlineEl.textContent = payload.headline || 'No headline available.';
            })
            .catch(() => {
                headlineEl.textContent = 'Headline unavailable right now.';
            });
    }

    updateHeadlineTicker(data) {
        const headlineEl = document.getElementById('headline-text');
        const yearEl = document.getElementById('news-year-label');
        if (!headlineEl) return;

        headlineEl.textContent = data && data.headline ? data.headline : 'Headline unavailable right now.';
        if (yearEl) {
            yearEl.textContent = data && data.year ? `Year: ${data.year}` : yearEl.textContent;
        }
    }

    handleModeToggled(data) {
        const modeToggle = document.getElementById('mode-toggle');
        if (modeToggle) {
            modeToggle.checked = data.practice_mode;
        }
        this.showToast(data.message, 'info');
    }

    formatCurrency(value) {
        return new Intl.NumberFormat('en-US', {
            style: 'currency',
            currency: 'USD',
            minimumFractionDigits: 2,
            maximumFractionDigits: 2
        }).format(value);
    }
}

const style = document.createElement('style');
style.textContent = `
.toast {
    position: fixed;
    top: 20px;
    right: 20px;
    background: rgba(20, 20, 25, 0.95);
    color: #f8fafc;
    padding: 14px 18px;
    border-radius: 14px;
    box-shadow: 0 18px 45px rgba(0, 0, 0, 0.25);
    opacity: 0;
    transform: translateY(-10px);
    transition: opacity 0.3s ease, transform 0.3s ease;
    z-index: 2000;
}
.toast.visible {
    opacity: 1;
    transform: translateY(0);
}
.toast.info { background: #0f172a; }
.toast.error { background: #831843; }
.toast.success { background: #14532d; }
`;
document.head.appendChild(style);

document.addEventListener('DOMContentLoaded', () => {
    window.stockSimulator = new StockSimulator();
});
