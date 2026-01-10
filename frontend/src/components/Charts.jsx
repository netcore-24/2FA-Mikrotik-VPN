import {
  BarChart,
  Bar,
  LineChart,
  Line,
  PieChart,
  Pie,
  Cell,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from 'recharts'

const COLORS = ['#667eea', '#764ba2', '#f093fb', '#4facfe', '#00f2fe', '#43e97b', '#fa709a']

const STATUS_COLORS = {
  pending: '#667eea',
  approved: '#764ba2',
  rejected: '#f093fb',
  active: '#4facfe',
  inactive: '#00f2fe',
}

const getColorByName = (name, index) => STATUS_COLORS[name] || COLORS[index % COLORS.length]

export const StatusPieChart = ({ data, title }) => {
  const rawData = Object.entries(data || {}).map(([name, value]) => ({
    name,
    value: Number(value) || 0,
  }))

  // Убираем нулевые сегменты, иначе подписи для 0% накладываются друг на друга
  const pieData = rawData.filter((d) => d.value > 0)

  if (pieData.length === 0) {
    return (
      <div className="chart-container">
        <h4>{title}</h4>
        <div className="chart-empty">Нет данных для отображения</div>
      </div>
    )
  }

  return (
    <div className="chart-container">
      <h4>{title}</h4>
      <ResponsiveContainer width="100%" height={300}>
        <PieChart>
          <Pie
            data={pieData}
            cx="50%"
            cy="50%"
            labelLine={false}
            label={({ name, percent }) => `${name}: ${(percent * 100).toFixed(0)}%`}
            outerRadius={80}
            fill="#8884d8"
            dataKey="value"
          >
            {pieData.map((entry, index) => (
              <Cell key={`cell-${entry.name}`} fill={getColorByName(entry.name, index)} />
            ))}
          </Pie>
          <Tooltip />
          <Legend
            payload={rawData.map((entry, index) => ({
              id: entry.name,
              type: 'square',
              value: entry.name,
              color: getColorByName(entry.name, index),
            }))}
          />
        </PieChart>
      </ResponsiveContainer>
    </div>
  )
}

export const StatusBarChart = ({ data, title }) => {
  const chartData = Object.entries(data || {}).map(([name, value]) => ({
    name,
    value,
  }))

  return (
    <div className="chart-container">
      <h4>{title}</h4>
      <ResponsiveContainer width="100%" height={300}>
        <BarChart data={chartData}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey="name" />
          <YAxis />
          <Tooltip />
          <Legend />
          <Bar dataKey="value" fill="#667eea" />
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}

export const TimeSeriesLineChart = ({ data, title, dataKey = 'value' }) => {
  return (
    <div className="chart-container">
      <h4>{title}</h4>
      <ResponsiveContainer width="100%" height={300}>
        <LineChart data={data || []}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey="date" />
          <YAxis />
          <Tooltip />
          <Legend />
          <Line type="monotone" dataKey={dataKey} stroke="#667eea" strokeWidth={2} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  )
}

export const MultiLineChart = ({ data, title, lines }) => {
  return (
    <div className="chart-container">
      <h4>{title}</h4>
      <ResponsiveContainer width="100%" height={300}>
        <LineChart data={data || []}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey="date" />
          <YAxis />
          <Tooltip />
          <Legend />
          {lines.map((line, index) => (
            <Line
              key={line.key}
              type="monotone"
              dataKey={line.key}
              stroke={COLORS[index % COLORS.length]}
              strokeWidth={2}
              name={line.name}
            />
          ))}
        </LineChart>
      </ResponsiveContainer>
    </div>
  )
}

export const StackedBarChart = ({ data, title, bars }) => {
  return (
    <div className="chart-container">
      <h4>{title}</h4>
      <ResponsiveContainer width="100%" height={300}>
        <BarChart data={data || []}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey="name" />
          <YAxis />
          <Tooltip />
          <Legend />
          {bars.map((bar, index) => (
            <Bar
              key={bar.key}
              dataKey={bar.key}
              stackId="a"
              fill={COLORS[index % COLORS.length]}
              name={bar.name}
            />
          ))}
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}
