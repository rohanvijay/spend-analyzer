import { useMemo, useState } from "react";
import {
  Area,
  AreaChart,
  Cell,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import transactionsJson from "../transactions.json";

const MONTHS = {
  Jan: 0,
  Feb: 1,
  Mar: 2,
  Apr: 3,
  May: 4,
  Jun: 5,
  Jul: 6,
  Aug: 7,
  Sep: 8,
  Oct: 9,
  Nov: 10,
  Dec: 11,
};

const MONTH_LABELS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
const MONTHLY_BUDGET = 4500;
const DEFAULT_CARD = "Venture X • 8356";
const DONUT_COLORS = ["#38bdf8", "#a78bfa", "#34d399", "#fbbf24", "#fb7185", "#f472b6", "#f8fafc"];
const CATEGORY_BADGES = {
  "Credit Card Payments": "border-emerald-400/20 bg-emerald-400/10 text-emerald-200",
  Groceries: "border-lime-400/20 bg-lime-400/10 text-lime-200",
  "Dining & Cafes": "border-amber-400/20 bg-amber-400/10 text-amber-200",
  Transportation: "border-sky-400/20 bg-sky-400/10 text-sky-200",
  "Utilities & Telecom": "border-cyan-400/20 bg-cyan-400/10 text-cyan-200",
  Subscriptions: "border-violet-400/20 bg-violet-400/10 text-violet-200",
  "Shopping & Retail": "border-fuchsia-400/20 bg-fuchsia-400/10 text-fuchsia-200",
  "Health & Fitness": "border-rose-400/20 bg-rose-400/10 text-rose-200",
  "Pet Care": "border-orange-400/20 bg-orange-400/10 text-orange-200",
  "Travel & Leisure": "border-indigo-400/20 bg-indigo-400/10 text-indigo-200",
  Other: "border-zinc-400/20 bg-zinc-400/10 text-zinc-300",
};

function cx(...classes) {
  return classes.filter(Boolean).join(" ");
}

function formatCurrency(value, compact = false) {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: compact ? 0 : 2,
    notation: compact ? "compact" : "standard",
  }).format(value);
}

function categoryBadgeClass(category) {
  return CATEGORY_BADGES[category] ?? "border-zinc-400/20 bg-zinc-400/10 text-zinc-300";
}

function parseStatementDate(date) {
  if (/^\d{1,2}\/\d{1,2}$/.test(String(date))) {
    const [month, day] = String(date).split("/").map(Number);
    const year = month > 5 ? 2025 : 2026;
    return new Date(year, month - 1, day);
  }

  const [month, day] = String(date).split(/\s+/);
  const year = month === "Dec" ? 2025 : 2026;
  return new Date(year, MONTHS[month] ?? 0, Number(day || 1));
}

function monthKey(date) {
  return `${date.getFullYear()}-${date.getMonth()}`;
}

function monthLabel(date) {
  return `${MONTH_LABELS[date.getMonth()]} ${date.getFullYear()}`;
}

function normalizeTransactions(rows) {
  return rows.map((row, index) => ({
    id: row.id ?? `${row.date}-${row.description}-${index}`,
    date: row.date,
    description: row.description,
    amount: Number(row.amount) || 0,
    card_source: row.card_source ?? DEFAULT_CARD,
    category: row.category || "Uncategorized",
    postedAt: parseStatementDate(row.date),
  })).map((transaction) => ({
    ...transaction,
    monthKey: monthKey(transaction.postedAt),
    monthLabel: monthLabel(transaction.postedAt),
  }));
}

function getMonthOptions(transactions) {
  const options = new Map();
  for (const transaction of transactions) {
    options.set(transaction.monthKey, {
      key: transaction.monthKey,
      label: transaction.monthLabel,
      date: new Date(transaction.postedAt.getFullYear(), transaction.postedAt.getMonth(), 1),
    });
  }

  return Array.from(options.values()).sort((a, b) => a.date - b.date);
}

function getCategoryOptions(transactions) {
  return Array.from(new Set(transactions.map((transaction) => transaction.category)))
    .sort((a, b) => a.localeCompare(b))
    .map((category) => ({ key: category, label: category }));
}

function getCardOptions(transactions) {
  return Array.from(new Set(transactions.map((transaction) => transaction.card_source)))
    .sort((a, b) => a.localeCompare(b))
    .map((card) => ({ key: card, label: card }));
}

function describeSelectedMonths(selectedKeys, monthOptions) {
  if (selectedKeys.length === monthOptions.length) {
    return "All months";
  }

  if (selectedKeys.length === 1) {
    return monthOptions.find((option) => option.key === selectedKeys[0])?.label ?? "Selected month";
  }

  return `${selectedKeys.length} months`;
}

function describeSelectedCategories(selectedKeys, categoryOptions) {
  if (selectedKeys.length === categoryOptions.length) {
    return "All categories";
  }

  if (selectedKeys.length === 1) {
    return selectedKeys[0];
  }

  return `${selectedKeys.length} categories`;
}

function describeSelectedCards(selectedKeys, cardOptions) {
  if (selectedKeys.length === cardOptions.length) {
    return "All cards";
  }

  if (selectedKeys.length === 1) {
    return selectedKeys[0];
  }

  return `${selectedKeys.length} cards`;
}

function buildDashboard(transactions, selectedMonthKeys, selectedCategoryKeys, selectedCardKeys, monthOptions, categoryOptions, cardOptions) {
  const selectedMonthSet = new Set(selectedMonthKeys);
  const selectedCategorySet = new Set(selectedCategoryKeys);
  const selectedCardSet = new Set(selectedCardKeys);
  const selectedTransactions = transactions.filter(
    (transaction) =>
      selectedMonthSet.has(transaction.monthKey) &&
      selectedCategorySet.has(transaction.category) &&
      selectedCardSet.has(transaction.card_source),
  );
  const charges = selectedTransactions.filter((transaction) => transaction.amount > 0);
  const credits = selectedTransactions.filter((transaction) => transaction.amount < 0);

  const monthlyMap = new Map();
  for (const transaction of charges) {
    const key = transaction.monthKey;
    const entry = monthlyMap.get(key) ?? {
      key,
      label: transaction.monthLabel,
      spend: 0,
      date: new Date(transaction.postedAt.getFullYear(), transaction.postedAt.getMonth(), 1),
    };
    entry.spend += transaction.amount;
    monthlyMap.set(key, entry);
  }

  const categoryMap = new Map();
  for (const transaction of charges) {
    categoryMap.set(transaction.category, (categoryMap.get(transaction.category) ?? 0) + transaction.amount);
  }

  const cardMap = new Map();
  for (const transaction of charges) {
    cardMap.set(transaction.card_source, (cardMap.get(transaction.card_source) ?? 0) + transaction.amount);
  }

  const monthlySpend = charges.reduce((total, transaction) => total + transaction.amount, 0);
  const creditTotal = Math.abs(credits.reduce((total, transaction) => total + transaction.amount, 0));
  const trend = Array.from(monthlyMap.values()).sort((a, b) => a.date - b.date);
  const categories = Array.from(categoryMap, ([name, value], index) => ({
    name,
    value,
    color: DONUT_COLORS[index % DONUT_COLORS.length],
  })).sort((a, b) => b.value - a.value);
  const cards = Array.from(cardMap, ([name, spend]) => ({ name, spend }));
  const periodBudget = MONTHLY_BUDGET * selectedMonthKeys.length;
  const periodLabel = describeSelectedMonths(selectedMonthKeys, monthOptions);
  const categoryLabel = describeSelectedCategories(selectedCategoryKeys, categoryOptions);
  const cardLabel = describeSelectedCards(selectedCardKeys, cardOptions);

  return {
    cards,
    cardLabel,
    categoryLabel,
    categories,
    creditTotal,
    periodBudget,
    periodLabel,
    monthlySpend,
    transactionCount: selectedTransactions.length,
    selectedTransactions,
    trend,
  };
}

function Shell({ children }) {
  return (
    <main className="min-h-screen bg-[radial-gradient(circle_at_top_left,rgba(56,189,248,0.16),transparent_32rem),linear-gradient(180deg,#090b10_0%,#050608_58%)] px-4 py-5 text-zinc-100 sm:px-6 lg:px-8">
      <div className="mx-auto flex w-full max-w-7xl flex-col gap-5">{children}</div>
    </main>
  );
}

function Header({ transactionCount }) {
  return (
    <header className="flex flex-col gap-3 border-b border-white/10 pb-5 sm:flex-row sm:items-end sm:justify-between">
      <div>
        <p className="text-xs font-medium uppercase tracking-[0.28em] text-sky-300">Rohan &amp; Manisha&apos;s Expense Tracker</p>
        <h1 className="mt-2 text-3xl font-semibold tracking-normal text-white sm:text-4xl">Spend dashboard</h1>
      </div>
      <div className="flex flex-wrap items-center gap-3 text-sm text-zinc-400 sm:justify-end">
        <span>{transactionCount} transactions</span>
      </div>
    </header>
  );
}

function MetricCard({ eyebrow, title, children, accent = "border-white/10" }) {
  return (
    <section className={cx("rounded-lg border bg-white/[0.045] p-5 shadow-2xl shadow-black/20 backdrop-blur", accent)}>
      <p className="text-xs font-medium uppercase tracking-[0.2em] text-zinc-500">{eyebrow}</p>
      <div className="mt-3">{title}</div>
      {children}
    </section>
  );
}

function Metrics({ data }) {
  const progress = Math.min((data.monthlySpend / data.periodBudget) * 100, 100);

  return (
    <section className="grid gap-4 md:grid-cols-3">
      <MetricCard
        eyebrow="Total monthly spend"
        title={<p className="text-3xl font-semibold text-white">{formatCurrency(data.monthlySpend)}</p>}
        accent="border-sky-400/30"
      >
        <p className="mt-3 text-sm text-zinc-400">{data.periodLabel} charges only</p>
      </MetricCard>

      <MetricCard
        eyebrow="Budget progress"
        title={
          <div className="flex items-end justify-between gap-4">
            <p className="text-3xl font-semibold text-white">{Math.round(progress)}%</p>
            <p className="pb-1 text-sm text-zinc-400">of {formatCurrency(data.periodBudget, true)}</p>
          </div>
        }
      >
        <div className="mt-5 h-2 overflow-hidden rounded-full bg-zinc-800">
          <div className="h-full rounded-full bg-sky-300 transition-all" style={{ width: `${progress}%` }} />
        </div>
        <p className="mt-3 text-sm text-zinc-400">
          {formatCurrency(Math.max(data.periodBudget - data.monthlySpend, 0))} remaining
        </p>
      </MetricCard>

      <MetricCard eyebrow="Active cards" title={<p className="text-3xl font-semibold text-white">{data.cards.length}</p>}>
        <div className="mt-4 space-y-3">
          {data.cards.map((card) => (
            <div key={card.name} className="flex items-center justify-between gap-3 text-sm">
              <span className="truncate text-zinc-300">{card.name}</span>
              <span className="font-medium text-white">{formatCurrency(card.spend, true)}</span>
            </div>
          ))}
        </div>
      </MetricCard>
    </section>
  );
}

function ChartPanel({ title, subtitle, children }) {
  return (
    <section className="rounded-lg border border-white/10 bg-white/[0.045] p-5 shadow-2xl shadow-black/20">
      <div className="mb-4 flex flex-col gap-1 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h2 className="text-lg font-semibold text-white">{title}</h2>
          <p className="text-sm text-zinc-500">{subtitle}</p>
        </div>
      </div>
      {children}
    </section>
  );
}

function SpendingTrend({ data }) {
  return (
    <ChartPanel title="Monthly spending trend" subtitle="Positive card charges grouped by transaction month">
      <div className="h-[320px] w-full">
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={data} margin={{ top: 10, right: 8, left: -18, bottom: 0 }}>
            <defs>
              <linearGradient id="spendFill" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#38bdf8" stopOpacity={0.42} />
                <stop offset="95%" stopColor="#38bdf8" stopOpacity={0.02} />
              </linearGradient>
            </defs>
            <XAxis dataKey="label" axisLine={false} tickLine={false} tick={{ fill: "#a1a1aa", fontSize: 12 }} dy={10} />
            <YAxis
              axisLine={false}
              tickLine={false}
              tick={{ fill: "#71717a", fontSize: 12 }}
              tickFormatter={(value) => formatCurrency(value, true)}
            />
            <Tooltip
              cursor={{ stroke: "#38bdf8", strokeOpacity: 0.18 }}
              contentStyle={{
                background: "#09090b",
                border: "1px solid rgba(255,255,255,0.12)",
                borderRadius: 8,
                color: "#fafafa",
              }}
              formatter={(value) => [formatCurrency(value), "Spend"]}
            />
            <Area
              type="monotone"
              dataKey="spend"
              stroke="#38bdf8"
              strokeWidth={3}
              fill="url(#spendFill)"
              dot={{ r: 4, fill: "#050608", stroke: "#38bdf8", strokeWidth: 2 }}
              activeDot={{ r: 6, fill: "#38bdf8", stroke: "#e0f2fe", strokeWidth: 2 }}
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </ChartPanel>
  );
}

function CategoryDonut({ data }) {
  const total = data.reduce((sum, category) => sum + category.value, 0);

  return (
    <ChartPanel title="Category mix" subtitle="Selected period proportions">
      <div className="grid gap-3 lg:grid-cols-[1fr_0.9fr]">
        <div className="relative h-[280px]">
          <ResponsiveContainer width="100%" height="100%">
            <PieChart>
              <Pie
                data={data}
                dataKey="value"
                nameKey="name"
                innerRadius={76}
                outerRadius={110}
                paddingAngle={3}
                stroke="#050608"
                strokeWidth={4}
              >
                {data.map((entry) => (
                  <Cell key={entry.name} fill={entry.color} />
                ))}
              </Pie>
              <Tooltip
                contentStyle={{
                  background: "#09090b",
                  border: "1px solid rgba(255,255,255,0.12)",
                  borderRadius: 8,
                  color: "#fafafa",
                }}
                formatter={(value) => [formatCurrency(value), "Spend"]}
              />
            </PieChart>
          </ResponsiveContainer>
          <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center">
            <span className="text-xs uppercase tracking-[0.2em] text-zinc-500">Period</span>
            <span className="mt-1 text-2xl font-semibold text-white">{formatCurrency(total, true)}</span>
          </div>
        </div>

        <div className="space-y-3 self-center">
          {data.map((category) => (
            <div key={category.name} className="flex items-center justify-between gap-4 px-1 py-1">
              <div className="flex min-w-0 items-center gap-3">
                <span className="h-2.5 w-2.5 shrink-0 rounded-full" style={{ backgroundColor: category.color }} />
                <span className="truncate text-sm text-zinc-300">{category.name}</span>
              </div>
              <span className="text-sm font-medium text-white">{total > 0 ? Math.round((category.value / total) * 100) : 0}%</span>
            </div>
          ))}
        </div>
      </div>
    </ChartPanel>
  );
}

function TransactionsTable({
  transactions,
  periodLabel,
  categoryLabel,
  cardLabel,
  monthOptions,
  categoryOptions,
  cardOptions,
  selectedMonthKey,
  selectedCategoryKey,
  selectedCardKey,
  onSelectMonth,
  onSelectCategory,
  onSelectCard,
}) {
  const [searchQuery, setSearchQuery] = useState("");
  const visibleTransactions = useMemo(() => {
    const normalizedSearch = searchQuery.trim().toLowerCase();

    return transactions.filter(
      (transaction) => !normalizedSearch || transaction.description.toLowerCase().includes(normalizedSearch),
    );
  }, [searchQuery, transactions]);

  return (
    <section className="rounded-lg border border-white/10 bg-white/[0.045] p-5 shadow-2xl shadow-black/20">
      <div className="mb-4 flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <h2 className="text-lg font-semibold text-white">Selected transactions</h2>
          <p className="text-sm text-zinc-500">
            {periodLabel} · {categoryLabel} · {cardLabel}
          </p>
        </div>
        <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
          <label className="relative block sm:w-72">
            <span className="sr-only">Search descriptions</span>
            <input
              type="search"
              value={searchQuery}
              onChange={(event) => setSearchQuery(event.target.value)}
              placeholder="Search descriptions"
              className="h-10 w-full rounded-md border border-white/10 bg-black/20 px-3 text-sm text-white outline-none transition placeholder:text-zinc-600 focus:border-sky-300/50 focus:ring-2 focus:ring-sky-300/10"
            />
          </label>
          <label className="block">
            <span className="sr-only">Filter by month</span>
            <select
              value={selectedMonthKey}
              onChange={(event) => onSelectMonth(event.target.value)}
              className="h-10 w-full rounded-md border border-white/10 bg-[#0d1016] px-3 text-sm text-zinc-200 outline-none transition focus:border-sky-300/50 focus:ring-2 focus:ring-sky-300/10 sm:w-40"
            >
              <option value="All">All months</option>
              {monthOptions.map((month) => (
                <option key={month.key} value={month.key}>
                  {month.label}
                </option>
              ))}
            </select>
          </label>
          <label className="block">
            <span className="sr-only">Filter by category</span>
            <select
              value={selectedCategoryKey}
              onChange={(event) => onSelectCategory(event.target.value)}
              className="h-10 w-full rounded-md border border-white/10 bg-[#0d1016] px-3 text-sm text-zinc-200 outline-none transition focus:border-sky-300/50 focus:ring-2 focus:ring-sky-300/10 sm:w-48"
            >
              <option value="All">All categories</option>
              {categoryOptions.map((category) => (
                <option key={category.key} value={category.key}>
                  {category.label}
                </option>
              ))}
            </select>
          </label>
          <label className="block">
            <span className="sr-only">Filter by card source</span>
            <select
              value={selectedCardKey}
              onChange={(event) => onSelectCard(event.target.value)}
              className="h-10 w-full rounded-md border border-white/10 bg-[#0d1016] px-3 text-sm text-zinc-200 outline-none transition focus:border-sky-300/50 focus:ring-2 focus:ring-sky-300/10 sm:w-56"
            >
              <option value="All">All cards</option>
              {cardOptions.map((card) => (
                <option key={card.key} value={card.key}>
                  {card.label}
                </option>
              ))}
            </select>
          </label>
        </div>
      </div>

      <div className="max-h-[560px] overflow-auto rounded-lg border border-white/10">
        <table className="w-full min-w-[920px] table-fixed border-collapse text-left text-sm">
          <thead className="sticky top-0 z-10 bg-[#15181d] text-xs uppercase tracking-[0.18em] text-zinc-500">
            <tr>
              <th className="w-20 px-4 py-3 font-medium">Date</th>
              <th className="px-4 py-3 font-medium">Description</th>
              <th className="w-44 px-4 py-3 font-medium">Card Source</th>
              <th className="w-44 px-4 py-3 font-medium">Category</th>
              <th className="w-28 px-4 py-3 text-right font-medium">Amount</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-white/10">
            {visibleTransactions.map((transaction) => (
              <tr key={transaction.id} className="hover:bg-white/[0.035]">
                <td className="px-4 py-3 text-zinc-400">{transaction.date}</td>
                <td className="truncate px-4 py-3 text-zinc-100">{transaction.description}</td>
                <td className="truncate px-4 py-3 text-zinc-400">{transaction.card_source}</td>
                <td className="px-4 py-3">
                  <span className={cx("inline-flex max-w-full items-center rounded-full border px-2.5 py-1 text-xs font-medium", categoryBadgeClass(transaction.category))}>
                    <span className="truncate">{transaction.category}</span>
                  </span>
                </td>
                <td className="px-4 py-3 text-right">
                  <span
                    className={cx(
                      "font-semibold tabular-nums",
                      transaction.amount < 0 ? "text-emerald-300" : "text-rose-200",
                    )}
                  >
                    {formatCurrency(transaction.amount)}
                  </span>
                </td>
              </tr>
            ))}
            {!visibleTransactions.length && (
              <tr>
                <td colSpan={5} className="px-4 py-10 text-center text-sm text-zinc-500">
                  No transactions match the current table filters.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
      <div className="mt-3 flex items-center justify-between gap-3 text-xs text-zinc-500">
        <span>
          Showing {visibleTransactions.length} of {transactions.length}
        </span>
        <span>Scroll to browse the full transaction log</span>
      </div>
    </section>
  );
}

export function App() {
  const transactions = useMemo(() => normalizeTransactions(transactionsJson), []);
  const monthOptions = useMemo(() => getMonthOptions(transactions), [transactions]);
  const categoryOptions = useMemo(() => getCategoryOptions(transactions), [transactions]);
  const cardOptions = useMemo(() => getCardOptions(transactions), [transactions]);
  const defaultMonthKeys = useMemo(() => monthOptions.slice(-1).map((month) => month.key), [monthOptions]);
  const defaultMonthKey = defaultMonthKeys[0] ?? "All";
  const [selectedMonthKey, setSelectedMonthKey] = useState(defaultMonthKey);
  const [selectedCategoryKey, setSelectedCategoryKey] = useState("All");
  const [selectedCardKey, setSelectedCardKey] = useState("All");
  const activeMonthKeys = selectedMonthKey === "All" ? monthOptions.map((month) => month.key) : [selectedMonthKey || defaultMonthKey];
  const activeCategoryKeys =
    selectedCategoryKey === "All" ? categoryOptions.map((category) => category.key) : [selectedCategoryKey];
  const activeCardKeys = selectedCardKey === "All" ? cardOptions.map((card) => card.key) : [selectedCardKey];
  const data = useMemo(
    () => buildDashboard(transactions, activeMonthKeys, activeCategoryKeys, activeCardKeys, monthOptions, categoryOptions, cardOptions),
    [activeCardKeys, activeCategoryKeys, activeMonthKeys, cardOptions, categoryOptions, monthOptions, transactions],
  );
  const selectedTransactions = useMemo(
    () => [...data.selectedTransactions].sort((a, b) => b.postedAt - a.postedAt),
    [data.selectedTransactions],
  );

  return (
    <Shell>
      <Header transactionCount={data.transactionCount} />
      <Metrics data={data} />
      <section className="grid gap-4 lg:grid-cols-[1.35fr_1fr]">
        <SpendingTrend data={data.trend} />
        <CategoryDonut data={data.categories} />
      </section>
      <TransactionsTable
        transactions={selectedTransactions}
        periodLabel={data.periodLabel}
        categoryLabel={data.categoryLabel}
        cardLabel={data.cardLabel}
        monthOptions={monthOptions}
        categoryOptions={categoryOptions}
        cardOptions={cardOptions}
        selectedMonthKey={selectedMonthKey || defaultMonthKey}
        selectedCategoryKey={selectedCategoryKey}
        selectedCardKey={selectedCardKey}
        onSelectMonth={setSelectedMonthKey}
        onSelectCategory={setSelectedCategoryKey}
        onSelectCard={setSelectedCardKey}
      />
    </Shell>
  );
}
