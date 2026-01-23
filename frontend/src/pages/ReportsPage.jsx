import React, { useState, useEffect } from 'react';
import { useAuthStore, api, formatCurrency, formatDate, formatDateTime } from '../lib/store';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/tabs';
import { Calendar } from '../components/ui/calendar';
import { Popover, PopoverContent, PopoverTrigger } from '../components/ui/popover';
import { Skeleton } from '../components/ui/skeleton';
import { toast } from 'sonner';
import { format } from 'date-fns';
import { jsPDF } from 'jspdf';
import autoTable from 'jspdf-autotable';
import { 
  BarChart3, 
  Download, 
  Calendar as CalendarIcon,
  TrendingUp,
  CreditCard,
  Trash2,
  FileText,
  Loader2
} from 'lucide-react';
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from 'recharts';

export default function ReportsPage() {
  const { user } = useAuthStore();
  const [activeTab, setActiveTab] = useState('sales');
  const [loading, setLoading] = useState(false);
  const [generating, setGenerating] = useState(false);
  
  // Date range
  const [startDate, setStartDate] = useState(new Date(new Date().setDate(1))); // First of month
  const [endDate, setEndDate] = useState(new Date());
  
  // Report data
  const [salesReport, setSalesReport] = useState(null);
  const [creditReport, setCreditReport] = useState(null);
  const [damagedReport, setDamagedReport] = useState(null);

  const formatDateForApi = (date) => date.toISOString();

  const loadSalesReport = async () => {
    setLoading(true);
    try {
      const data = await api.get(
        `/reports/sales?start_date=${formatDateForApi(startDate)}&end_date=${formatDateForApi(endDate)}`
      );
      setSalesReport(data);
    } catch (error) {
      toast.error('Failed to load sales report');
    } finally {
      setLoading(false);
    }
  };

  const loadCreditReport = async () => {
    setLoading(true);
    try {
      const data = await api.get('/reports/credit');
      setCreditReport(data);
    } catch (error) {
      toast.error('Failed to load credit report');
    } finally {
      setLoading(false);
    }
  };

  const loadDamagedReport = async () => {
    setLoading(true);
    try {
      const data = await api.get(
        `/reports/damaged?start_date=${formatDateForApi(startDate)}&end_date=${formatDateForApi(endDate)}`
      );
      setDamagedReport(data);
    } catch (error) {
      toast.error('Failed to load damaged report');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (activeTab === 'sales') loadSalesReport();
    else if (activeTab === 'credit') loadCreditReport();
    else if (activeTab === 'damaged') loadDamagedReport();
  }, [activeTab]);

  const handleDateChange = () => {
    if (activeTab === 'sales') loadSalesReport();
    else if (activeTab === 'damaged') loadDamagedReport();
  };

  const generateSalesPDF = async () => {
    setGenerating(true);
    try {
      const doc = new jsPDF();
      
      // Header
      doc.setFontSize(20);
      doc.setTextColor(0, 123, 255);
      doc.text('CloudDuka', 105, 20, { align: 'center' });
      doc.setFontSize(16);
      doc.setTextColor(0, 0, 0);
      doc.text('Sales Report', 105, 30, { align: 'center' });
      doc.setFontSize(10);
      doc.text(`Period: ${format(startDate, 'PP')} - ${format(endDate, 'PP')}`, 105, 38, { align: 'center' });
      
      // Summary
      doc.setFontSize(12);
      doc.text(`Total Sales: ${formatCurrency(salesReport?.summary?.total || 0)}`, 14, 55);
      doc.text(`Transactions: ${salesReport?.summary?.count || 0}`, 14, 63);
      
      // Table
      const tableData = (salesReport?.sales || []).slice(0, 100).map((sale) => [
        sale.receipt_number,
        format(new Date(sale.created_at), 'PP'),
        sale.payment_method.toUpperCase(),
        formatCurrency(sale.total_amount),
        sale.status
      ]);
      
      autoTable(doc, {
        startY: 75,
        head: [['Receipt #', 'Date', 'Method', 'Amount', 'Status']],
        body: tableData,
        theme: 'striped',
        headStyles: { fillColor: [0, 123, 255] },
      });
      
      doc.save(`sales_report_${format(startDate, 'yyyy-MM-dd')}_${format(endDate, 'yyyy-MM-dd')}.pdf`);
      toast.success('PDF downloaded');
    } catch (error) {
      toast.error('Failed to generate PDF');
    } finally {
      setGenerating(false);
    }
  };

  const generateCreditPDF = async () => {
    setGenerating(true);
    try {
      const doc = new jsPDF();
      
      doc.setFontSize(20);
      doc.setTextColor(255, 140, 0);
      doc.text('CloudDuka', 105, 20, { align: 'center' });
      doc.setFontSize(16);
      doc.setTextColor(0, 0, 0);
      doc.text('Credit Report', 105, 30, { align: 'center' });
      doc.setFontSize(10);
      doc.text(`Generated: ${format(new Date(), 'PPpp')}`, 105, 38, { align: 'center' });
      
      doc.setFontSize(12);
      doc.text(`Total Outstanding: ${formatCurrency(creditReport?.summary?.total_outstanding || 0)}`, 14, 55);
      doc.text(`Customers with Balance: ${creditReport?.summary?.customers_with_balance || 0}`, 14, 63);
      
      const tableData = (creditReport?.customers || []).map((c) => [
        c.name,
        c.phone,
        formatCurrency(c.current_balance),
        formatCurrency(c.credit_limit)
      ]);
      
      autoTable(doc, {
        startY: 75,
        head: [['Customer', 'Phone', 'Balance', 'Limit']],
        body: tableData,
        theme: 'striped',
        headStyles: { fillColor: [255, 140, 0] },
      });
      
      doc.save(`credit_report_${format(new Date(), 'yyyy-MM-dd')}.pdf`);
      toast.success('PDF downloaded');
    } catch (error) {
      toast.error('Failed to generate PDF');
    } finally {
      setGenerating(false);
    }
  };

  const generateDamagedPDF = async () => {
    setGenerating(true);
    try {
      const doc = new jsPDF();
      
      doc.setFontSize(20);
      doc.setTextColor(220, 38, 38);
      doc.text('CloudDuka', 105, 20, { align: 'center' });
      doc.setFontSize(16);
      doc.setTextColor(0, 0, 0);
      doc.text('Damaged/Spoiled Stock Report', 105, 30, { align: 'center' });
      doc.setFontSize(10);
      doc.text(`Period: ${format(startDate, 'PP')} - ${format(endDate, 'PP')}`, 105, 38, { align: 'center' });
      
      doc.setFontSize(12);
      doc.text(`Total Items: ${damagedReport?.summary?.total_quantity || 0}`, 14, 55);
      
      const tableData = (damagedReport?.items || []).map((item) => [
        item.product_name,
        item.quantity.toString(),
        item.reason,
        format(new Date(item.created_at), 'PP'),
        item.notes || '-'
      ]);
      
      autoTable(doc, {
        startY: 75,
        head: [['Product', 'Qty', 'Reason', 'Date', 'Notes']],
        body: tableData,
        theme: 'striped',
        headStyles: { fillColor: [220, 38, 38] },
      });
      
      doc.save(`damaged_report_${format(startDate, 'yyyy-MM-dd')}_${format(endDate, 'yyyy-MM-dd')}.pdf`);
      toast.success('PDF downloaded');
    } catch (error) {
      toast.error('Failed to generate PDF');
    } finally {
      setGenerating(false);
    }
  };

  const paymentMethodData = salesReport?.summary?.by_payment_method 
    ? Object.entries(salesReport.summary.by_payment_method).map(([method, amount]) => ({
        method: method.charAt(0).toUpperCase() + method.slice(1),
        amount,
      }))
    : [];

  const COLORS = { Cash: '#22c55e', Mpesa: '#10b981', Credit: '#f59e0b' };

  return (
    <div className="p-4 space-y-4" data-testid="reports-page">
      {/* Header */}
      <h1 className="text-2xl font-bold" style={{ fontFamily: 'Outfit, sans-serif' }}>
        Reports
      </h1>

      {/* Tabs */}
      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList className="w-full grid grid-cols-3">
          <TabsTrigger value="sales" data-testid="sales-report-tab">
            <TrendingUp className="h-4 w-4 mr-1" />
            Sales
          </TabsTrigger>
          <TabsTrigger value="credit" data-testid="credit-report-tab">
            <CreditCard className="h-4 w-4 mr-1" />
            Credit
          </TabsTrigger>
          <TabsTrigger value="damaged" data-testid="damaged-report-tab">
            <Trash2 className="h-4 w-4 mr-1" />
            Damaged
          </TabsTrigger>
        </TabsList>

        {/* Date Range Picker (for Sales and Damaged) */}
        {(activeTab === 'sales' || activeTab === 'damaged') && (
          <Card className="mt-4">
            <CardContent className="p-4">
              <div className="flex flex-wrap gap-3 items-end">
                <div className="flex-1 min-w-[140px]">
                  <Label className="text-xs">From</Label>
                  <Popover>
                    <PopoverTrigger asChild>
                      <Button variant="outline" className="w-full justify-start text-left font-normal">
                        <CalendarIcon className="mr-2 h-4 w-4" />
                        {format(startDate, 'PP')}
                      </Button>
                    </PopoverTrigger>
                    <PopoverContent className="w-auto p-0">
                      <Calendar
                        mode="single"
                        selected={startDate}
                        onSelect={(d) => d && setStartDate(d)}
                        initialFocus
                      />
                    </PopoverContent>
                  </Popover>
                </div>
                <div className="flex-1 min-w-[140px]">
                  <Label className="text-xs">To</Label>
                  <Popover>
                    <PopoverTrigger asChild>
                      <Button variant="outline" className="w-full justify-start text-left font-normal">
                        <CalendarIcon className="mr-2 h-4 w-4" />
                        {format(endDate, 'PP')}
                      </Button>
                    </PopoverTrigger>
                    <PopoverContent className="w-auto p-0">
                      <Calendar
                        mode="single"
                        selected={endDate}
                        onSelect={(d) => d && setEndDate(d)}
                        initialFocus
                      />
                    </PopoverContent>
                  </Popover>
                </div>
                <Button onClick={handleDateChange} className="bg-[#007BFF]" data-testid="apply-date-btn">
                  Apply
                </Button>
              </div>
            </CardContent>
          </Card>
        )}

        {/* Sales Report Tab */}
        <TabsContent value="sales" className="space-y-4 mt-4">
          {loading ? (
            <div className="space-y-4">
              <Skeleton className="h-32 rounded-xl" />
              <Skeleton className="h-48 rounded-xl" />
            </div>
          ) : salesReport ? (
            <>
              {/* Summary */}
              <div className="grid grid-cols-2 gap-4">
                <Card className="bg-green-50 border-green-200">
                  <CardContent className="p-4">
                    <p className="text-sm text-green-600">Total Sales</p>
                    <p className="text-2xl font-bold text-green-700" style={{ fontFamily: 'Outfit, sans-serif' }}>
                      {formatCurrency(salesReport.summary?.total || 0)}
                    </p>
                  </CardContent>
                </Card>
                <Card>
                  <CardContent className="p-4">
                    <p className="text-sm text-slate-500">Transactions</p>
                    <p className="text-2xl font-bold" style={{ fontFamily: 'Outfit, sans-serif' }}>
                      {salesReport.summary?.count || 0}
                    </p>
                  </CardContent>
                </Card>
              </div>

              {/* Chart */}
              {paymentMethodData.length > 0 && (
                <Card>
                  <CardHeader className="pb-2">
                    <CardTitle className="text-lg">By Payment Method</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="h-48">
                      <ResponsiveContainer width="100%" height="100%">
                        <BarChart data={paymentMethodData}>
                          <XAxis dataKey="method" axisLine={false} tickLine={false} />
                          <YAxis axisLine={false} tickLine={false} tickFormatter={(v) => `${(v/1000).toFixed(0)}K`} />
                          <Tooltip formatter={(v) => formatCurrency(v)} />
                          <Bar dataKey="amount" radius={[8, 8, 0, 0]}>
                            {paymentMethodData.map((entry, index) => (
                              <Cell key={`cell-${index}`} fill={COLORS[entry.method] || '#007BFF'} />
                            ))}
                          </Bar>
                        </BarChart>
                      </ResponsiveContainer>
                    </div>
                  </CardContent>
                </Card>
              )}

              {/* Download Button */}
              <Button 
                className="w-full bg-[#007BFF]"
                onClick={generateSalesPDF}
                disabled={generating}
                data-testid="download-sales-pdf-btn"
              >
                {generating ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Download className="mr-2 h-4 w-4" />}
                Download PDF Report
              </Button>

              {/* Recent Sales */}
              <Card>
                <CardHeader className="pb-2">
                  <CardTitle className="text-lg">Recent Transactions</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="space-y-2 max-h-64 overflow-y-auto">
                    {(salesReport.sales || []).slice(0, 20).map((sale) => (
                      <div key={sale.id} className="flex justify-between items-center p-3 bg-slate-50 rounded-lg">
                        <div>
                          <p className="font-medium text-sm">{sale.receipt_number}</p>
                          <p className="text-xs text-slate-500">{formatDateTime(sale.created_at)}</p>
                        </div>
                        <div className="text-right">
                          <p className="font-bold">{formatCurrency(sale.total_amount)}</p>
                          <span className={`text-xs px-2 py-0.5 rounded-full ${
                            sale.payment_method === 'cash' ? 'bg-green-100 text-green-700' :
                            sale.payment_method === 'mpesa' ? 'bg-emerald-100 text-emerald-700' :
                            'bg-orange-100 text-orange-700'
                          }`}>
                            {sale.payment_method}
                          </span>
                        </div>
                      </div>
                    ))}
                  </div>
                </CardContent>
              </Card>
            </>
          ) : null}
        </TabsContent>

        {/* Credit Report Tab */}
        <TabsContent value="credit" className="space-y-4 mt-4">
          {loading ? (
            <div className="space-y-4">
              <Skeleton className="h-32 rounded-xl" />
              <Skeleton className="h-48 rounded-xl" />
            </div>
          ) : creditReport ? (
            <>
              <div className="grid grid-cols-2 gap-4">
                <Card className="bg-orange-50 border-orange-200">
                  <CardContent className="p-4">
                    <p className="text-sm text-orange-600">Total Outstanding</p>
                    <p className="text-2xl font-bold text-orange-700" style={{ fontFamily: 'Outfit, sans-serif' }}>
                      {formatCurrency(creditReport.summary?.total_outstanding || 0)}
                    </p>
                  </CardContent>
                </Card>
                <Card>
                  <CardContent className="p-4">
                    <p className="text-sm text-slate-500">With Balance</p>
                    <p className="text-2xl font-bold" style={{ fontFamily: 'Outfit, sans-serif' }}>
                      {creditReport.summary?.customers_with_balance || 0}
                    </p>
                  </CardContent>
                </Card>
              </div>

              <Button 
                className="w-full bg-[#FF8C00]"
                onClick={generateCreditPDF}
                disabled={generating}
                data-testid="download-credit-pdf-btn"
              >
                {generating ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Download className="mr-2 h-4 w-4" />}
                Download PDF Report
              </Button>

              <Card>
                <CardHeader className="pb-2">
                  <CardTitle className="text-lg">Credit Customers</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="space-y-2 max-h-64 overflow-y-auto">
                    {(creditReport.customers || []).map((c) => (
                      <div key={c.id} className="flex justify-between items-center p-3 bg-slate-50 rounded-lg">
                        <div>
                          <p className="font-medium">{c.name}</p>
                          <p className="text-xs text-slate-500">{c.phone}</p>
                        </div>
                        <p className={`font-bold ${c.current_balance > 0 ? 'text-orange-600' : 'text-green-600'}`}>
                          {formatCurrency(c.current_balance)}
                        </p>
                      </div>
                    ))}
                  </div>
                </CardContent>
              </Card>
            </>
          ) : null}
        </TabsContent>

        {/* Damaged Report Tab */}
        <TabsContent value="damaged" className="space-y-4 mt-4">
          {loading ? (
            <div className="space-y-4">
              <Skeleton className="h-32 rounded-xl" />
              <Skeleton className="h-48 rounded-xl" />
            </div>
          ) : damagedReport ? (
            <>
              <div className="grid grid-cols-2 gap-4">
                <Card className="bg-red-50 border-red-200">
                  <CardContent className="p-4">
                    <p className="text-sm text-red-600">Total Items Lost</p>
                    <p className="text-2xl font-bold text-red-700" style={{ fontFamily: 'Outfit, sans-serif' }}>
                      {damagedReport.summary?.total_quantity || 0}
                    </p>
                  </CardContent>
                </Card>
                <Card>
                  <CardContent className="p-4">
                    <p className="text-sm text-slate-500">Records</p>
                    <p className="text-2xl font-bold" style={{ fontFamily: 'Outfit, sans-serif' }}>
                      {damagedReport.summary?.total_items || 0}
                    </p>
                  </CardContent>
                </Card>
              </div>

              {/* By Reason */}
              {damagedReport.summary?.by_reason && Object.keys(damagedReport.summary.by_reason).length > 0 && (
                <Card>
                  <CardHeader className="pb-2">
                    <CardTitle className="text-lg">By Reason</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="flex flex-wrap gap-2">
                      {Object.entries(damagedReport.summary.by_reason).map(([reason, qty]) => (
                        <span key={reason} className={`px-3 py-1.5 rounded-full text-sm font-medium ${
                          reason === 'damaged' ? 'bg-red-100 text-red-700' :
                          reason === 'expired' ? 'bg-amber-100 text-amber-700' :
                          reason === 'spoiled' ? 'bg-orange-100 text-orange-700' :
                          'bg-slate-100 text-slate-700'
                        }`}>
                          {reason}: {qty}
                        </span>
                      ))}
                    </div>
                  </CardContent>
                </Card>
              )}

              <Button 
                className="w-full bg-red-600"
                onClick={generateDamagedPDF}
                disabled={generating}
                data-testid="download-damaged-pdf-btn"
              >
                {generating ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Download className="mr-2 h-4 w-4" />}
                Download PDF Report
              </Button>

              <Card>
                <CardHeader className="pb-2">
                  <CardTitle className="text-lg">Damaged Items</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="space-y-2 max-h-64 overflow-y-auto">
                    {(damagedReport.items || []).map((item) => (
                      <div key={item.id} className="flex justify-between items-center p-3 bg-slate-50 rounded-lg">
                        <div>
                          <p className="font-medium">{item.product_name}</p>
                          <p className="text-xs text-slate-500">{formatDate(item.created_at)} • {item.reason}</p>
                        </div>
                        <p className="font-bold text-red-600">-{item.quantity}</p>
                      </div>
                    ))}
                  </div>
                </CardContent>
              </Card>
            </>
          ) : null}
        </TabsContent>
      </Tabs>
    </div>
  );
}
