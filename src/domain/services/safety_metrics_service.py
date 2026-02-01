"""Safety Metrics and Monitoring Service for RAG System"""

from typing import List, Dict, Any, Optional, Tuple
import logging
import asyncio
from dataclasses import dataclass, asdict
from enum import Enum
from datetime import datetime, timedelta
import json
from collections import defaultdict, deque
import statistics

from .enhanced_safety_guard import SafetyDecision, RiskLevel, FallbackStrategy
from .llama_guard_service import SafetyAnalysis, SafetyCategory
from .hallucination_detector import HallucinationResult, HallucinationType


logger = logging.getLogger(__name__)


class MetricType(Enum):
    """Types of safety metrics"""
    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"
    TIMER = "timer"


@dataclass
class SafetyMetric:
    """Individual safety metric"""
    name: str
    metric_type: MetricType
    value: float
    labels: Dict[str, str]
    timestamp: datetime
    description: str = ""


@dataclass
class SafetyMetricsConfig:
    """Configuration for safety metrics collection"""
    enable_real_time_metrics: bool = True
    metrics_retention_days: int = 30
    alert_thresholds: Dict[str, float] = None
    enable_anomaly_detection: bool = True
    anomaly_window_size: int = 100
    enable_trend_analysis: bool = True
    trend_window_hours: int = 24
    export_metrics: bool = True
    export_interval_minutes: int = 5
    
    def __post_init__(self):
        if self.alert_thresholds is None:
            self.alert_thresholds = {
                "high_risk_requests_per_minute": 10,
                "hallucination_rate": 0.2,
                "safety_failure_rate": 0.05,
                "circuit_breaker_triggers_per_hour": 5,
                "human_review_rate": 0.1
            }


class SafetyMetricsCollector:
    """Collects and manages safety metrics"""
    
    def __init__(self, config: SafetyMetricsConfig):
        self.config = config
        self.metrics: deque = deque(maxlen=10000)  # Rolling buffer
        self.counters: defaultdict = defaultdict(lambda: defaultdict(int))
        self.gauges: defaultdict = defaultdict(lambda: defaultdict(float))
        self.histograms: defaultdict = defaultdict(lambda: defaultdict(list))
        self.timers: defaultdict = defaultdict(lambda: defaultdict(list))
        self.alerts: List[Dict[str, Any]] = []
        
    def record_metric(self, metric: SafetyMetric):
        """Record a safety metric"""
        self.metrics.append(metric)
        
        # Update specific metric type storage
        if metric.metric_type == MetricType.COUNTER:
            self.counters[metric.name][frozenset(metric.labels.items())] += metric.value
        elif metric.metric_type == MetricType.GAUGE:
            self.gauges[metric.name][frozenset(metric.labels.items())] = metric.value
        elif metric.metric_type == MetricType.HISTOGRAM:
            self.histograms[metric.name][frozenset(metric.labels.items())].append(metric.value)
        elif metric.metric_type == MetricType.TIMER:
            self.timers[metric.name][frozenset(metric.labels.items())].append(metric.value)
        
        # Check for alerts
        if self.config.enable_real_time_metrics:
            self._check_alerts(metric)
    
    def increment_counter(self, name: str, value: float = 1.0, labels: Dict[str, str] = None):
        """Increment a counter metric"""
        metric = SafetyMetric(
            name=name,
            metric_type=MetricType.COUNTER,
            value=value,
            labels=labels or {},
            timestamp=datetime.now(),
            description=f"Counter metric: {name}"
        )
        self.record_metric(metric)
    
    def set_gauge(self, name: str, value: float, labels: Dict[str, str] = None):
        """Set a gauge metric"""
        metric = SafetyMetric(
            name=name,
            metric_type=MetricType.GAUGE,
            value=value,
            labels=labels or {},
            timestamp=datetime.now(),
            description=f"Gauge metric: {name}"
        )
        self.record_metric(metric)
    
    def record_histogram(self, name: str, value: float, labels: Dict[str, str] = None):
        """Record a histogram metric"""
        metric = SafetyMetric(
            name=name,
            metric_type=MetricType.HISTOGRAM,
            value=value,
            labels=labels or {},
            timestamp=datetime.now(),
            description=f"Histogram metric: {name}"
        )
        self.record_metric(metric)
    
    def record_timer(self, name: str, duration_ms: float, labels: Dict[str, str] = None):
        """Record a timer metric"""
        metric = SafetyMetric(
            name=name,
            metric_type=MetricType.TIMER,
            value=duration_ms,
            labels=labels or {},
            timestamp=datetime.now(),
            description=f"Timer metric: {name}"
        )
        self.record_metric(metric)
    
    def _check_alerts(self, metric: SafetyMetric):
        """Check if metric triggers any alerts"""
        threshold = self.config.alert_thresholds.get(metric.name)
        if threshold and metric.value > threshold:
            alert = {
                "metric_name": metric.name,
                "current_value": metric.value,
                "threshold": threshold,
                "timestamp": datetime.now().isoformat(),
                "labels": metric.labels,
                "severity": "high" if metric.value > threshold * 1.5 else "medium"
            }
            self.alerts.append(alert)
            logger.warning(f"Safety alert triggered: {alert}")
    
    def get_metrics_summary(self, time_window_minutes: int = 60) -> Dict[str, Any]:
        """Get summary of metrics for a time window"""
        cutoff_time = datetime.now() - timedelta(minutes=time_window_minutes)
        recent_metrics = [m for m in self.metrics if m.timestamp >= cutoff_time]
        
        summary = {
            "time_window_minutes": time_window_minutes,
            "total_metrics": len(recent_metrics),
            "metrics_by_type": defaultdict(int),
            "top_metrics": {},
            "alerts_count": len([a for a in self.alerts if datetime.fromisoformat(a["timestamp"]) >= cutoff_time])
        }
        
        # Count by type
        for metric in recent_metrics:
            summary["metrics_by_type"][metric.metric_type.value] += 1
        
        # Top metrics by frequency
        metric_counts = defaultdict(int)
        for metric in recent_metrics:
            metric_counts[metric.name] += 1
        
        summary["top_metrics"] = dict(sorted(metric_counts.items(), key=lambda x: x[1], reverse=True)[:10])
        
        return dict(summary)


class SafetyAnalyzer:
    """Analyzes safety metrics and provides insights"""
    
    def __init__(self, metrics_collector: SafetyMetricsCollector):
        self.metrics_collector = metrics_collector
    
    async def analyze_safety_trends(self, hours: int = 24) -> Dict[str, Any]:
        """Analyze safety trends over time"""
        cutoff_time = datetime.now() - timedelta(hours=hours)
        recent_metrics = [m for m in self.metrics_collector.metrics if m.timestamp >= cutoff_time]
        
        # Group by hour
        hourly_data = defaultdict(lambda: defaultdict(list))
        for metric in recent_metrics:
            hour_key = metric.timestamp.replace(minute=0, second=0, microsecond=0)
            hourly_data[hour_key][metric.name].append(metric.value)
        
        # Calculate trends
        trends = {}
        for metric_name in set(m.name for m in recent_metrics):
            hourly_values = []
            for hour in sorted(hourly_data.keys()):
                if metric_name in hourly_data[hour]:
                    hourly_values.append(statistics.mean(hourly_data[hour][metric_name]))
                else:
                    hourly_values.append(0)
            
            if len(hourly_values) > 1:
                # Simple trend calculation
                trend = (hourly_values[-1] - hourly_values[0]) / len(hourly_values)
                trends[metric_name] = {
                    "trend": trend,
                    "direction": "increasing" if trend > 0 else "decreasing" if trend < 0 else "stable",
                    "hourly_values": hourly_values
                }
        
        return {
            "analysis_period_hours": hours,
            "trends": trends,
            "data_points": len(recent_metrics)
        }
    
    async def detect_anomalies(self) -> List[Dict[str, Any]]:
        """Detect anomalies in safety metrics"""
        anomalies = []
        
        for metric_name, label_groups in self.metrics_collector.histograms.items():
            for labels, values in label_groups.items():
                if len(values) < self.metrics_collector.config.anomaly_window_size:
                    continue
                
                # Simple statistical anomaly detection
                recent_values = values[-self.metrics_collector.config.anomaly_window_size:]
                mean_val = statistics.mean(recent_values)
                std_val = statistics.stdev(recent_values) if len(recent_values) > 1 else 0
                
                # Check for outliers (3 sigma rule)
                for i, value in enumerate(recent_values):
                    if std_val > 0 and abs(value - mean_val) > 3 * std_val:
                        anomalies.append({
                            "metric_name": metric_name,
                            "labels": dict(labels),
                            "anomalous_value": value,
                            "mean": mean_val,
                            "std": std_val,
                            "z_score": (value - mean_val) / std_val if std_val > 0 else 0,
                            "timestamp": datetime.now().isoformat()
                        })
        
        return anomalies
    
    async def generate_safety_report(self) -> Dict[str, Any]:
        """Generate comprehensive safety report"""
        # Get recent metrics
        recent_summary = self.metrics_collector.get_metrics_summary(time_window_minutes=60)
        
        # Analyze trends
        trends = await self.analyze_safety_trends(hours=24)
        
        # Detect anomalies
        anomalies = await self.detect_anomalies()
        
        # Calculate key safety KPIs
        kpis = self._calculate_safety_kpis()
        
        # Get recent alerts
        recent_alerts = [
            alert for alert in self.metrics_collector.alerts
            if datetime.fromisoformat(alert["timestamp"]) >= datetime.now() - timedelta(hours=1)
        ]
        
        return {
            "report_timestamp": datetime.now().isoformat(),
            "metrics_summary": recent_summary,
            "trends": trends,
            "anomalies": anomalies,
            "safety_kpis": kpis,
            "recent_alerts": recent_alerts,
            "recommendations": self._generate_recommendations(kpis, trends, anomalies)
        }
    
    def _calculate_safety_kpis(self) -> Dict[str, Any]:
        """Calculate key safety performance indicators"""
        # Get metrics from last hour
        cutoff_time = datetime.now() - timedelta(hours=1)
        recent_metrics = [m for m in self.metrics_collector.metrics if m.timestamp >= cutoff_time]
        
        kpis = {}
        
        # Request rejection rate
        total_requests = len([m for m in recent_metrics if m.name == "safety_validation_total"])
        rejected_requests = len([m for m in recent_metrics if m.name == "safety_validation_rejected"])
        if total_requests > 0:
            kpis["rejection_rate"] = rejected_requests / total_requests
        
        # Hallucination rate
        hallucination_checks = len([m for m in recent_metrics if m.name == "hallucination_detection_total"])
        hallucinations_detected = len([m for m in recent_metrics if m.name == "hallucination_detected"])
        if hallucination_checks > 0:
            kpis["hallucination_rate"] = hallucinations_detected / hallucination_checks
        
        # Average risk score
        risk_scores = [m.value for m in recent_metrics if m.name == "risk_score"]
        if risk_scores:
            kpis["average_risk_score"] = statistics.mean(risk_scores)
        
        # Circuit breaker triggers
        circuit_triggers = len([m for m in recent_metrics if m.name == "circuit_breaker_triggered"])
        kpis["circuit_breaker_triggers"] = circuit_triggers
        
        # Human review rate
        human_reviews = len([m for m in recent_metrics if m.name == "human_review_required"])
        if total_requests > 0:
            kpis["human_review_rate"] = human_reviews / total_requests
        
        return kpis
    
    def _generate_recommendations(
        self, 
        kpis: Dict[str, Any], 
        trends: Dict[str, Any], 
        anomalies: List[Dict[str, Any]]
    ) -> List[str]:
        """Generate safety improvement recommendations"""
        recommendations = []
        
        # Based on KPIs
        if kpis.get("rejection_rate", 0) > 0.1:
            recommendations.append("High rejection rate detected. Consider adjusting safety thresholds or improving input quality.")
        
        if kpis.get("hallucination_rate", 0) > 0.2:
            recommendations.append("High hallucination rate. Review retrieval quality and context relevance.")
        
        if kpis.get("average_risk_score", 0) > 0.6:
            recommendations.append("High average risk scores. Review safety configuration and user patterns.")
        
        if kpis.get("circuit_breaker_triggers", 0) > 5:
            recommendations.append("Frequent circuit breaker triggers. Check service health and capacity.")
        
        # Based on trends
        for metric_name, trend_data in trends.get("trends", {}).items():
            if "risk" in metric_name.lower() and trend_data["direction"] == "increasing":
                recommendations.append(f"Increasing risk trend in {metric_name}. Investigate underlying causes.")
        
        # Based on anomalies
        if len(anomalies) > 5:
            recommendations.append("Multiple anomalies detected. Review system stability and data quality.")
        
        if not recommendations:
            recommendations.append("Safety metrics are within normal ranges. Continue monitoring.")
        
        return recommendations


class SafetyMetricsService:
    """Main service for safety metrics collection and analysis"""
    
    def __init__(self, config: SafetyMetricsConfig = None):
        self.config = config or SafetyMetricsConfig()
        self.collector = SafetyMetricsCollector(self.config)
        self.analyzer = SafetyAnalyzer(self.collector)
        self._start_background_tasks()
    
    def _start_background_tasks(self):
        """Start background metric collection tasks"""
        if self.config.enable_real_time_metrics:
            asyncio.create_task(self._periodic_metrics_export())
    
    async def _periodic_metrics_export(self):
        """Periodically export metrics"""
        while True:
            try:
                await asyncio.sleep(self.config.export_interval_minutes * 60)
                if self.config.export_metrics:
                    await self._export_metrics()
            except Exception as e:
                logger.error(f"Metrics export failed: {e}")
    
    async def _export_metrics(self):
        """Export metrics to external systems"""
        # This would integrate with Prometheus, ClickHouse, etc.
        logger.info("Exporting safety metrics")
        # Implementation depends on specific export targets
    
    def record_safety_decision(self, decision: SafetyDecision, processing_time_ms: float):
        """Record metrics from safety decision"""
        labels = {
            "risk_level": decision.risk_level.value,
            "fallback_strategy": decision.fallback_strategy.value
        }
        
        # Record decision
        self.collector.increment_counter("safety_validation_total", labels=labels)
        
        if not decision.allowed:
            self.collector.increment_counter("safety_validation_rejected", labels=labels)
        
        if decision.requires_human_review:
            self.collector.increment_counter("human_review_required", labels=labels)
        
        # Record risk score
        self.collector.record_histogram("risk_score", 1.0 - decision.confidence, labels=labels)
        
        # Record processing time
        self.collector.record_timer("safety_validation_duration_ms", processing_time_ms)
    
    def record_hallucination_detection(self, result: HallucinationResult):
        """Record metrics from hallucination detection"""
        labels = {
            "hallucination_detected": str(result.is_hallucinated),
            "confidence_level": result.confidence_level.value
        }
        
        self.collector.increment_counter("hallucination_detection_total", labels=labels)
        
        if result.is_hallucinated:
            self.collector.increment_counter("hallucination_detected", labels=labels)
            
            # Record hallucination types
            for halluc_type in result.hallucination_types:
                type_labels = {**labels, "hallucination_type": halluc_type.value}
                self.collector.increment_counter("hallucination_by_type", labels=type_labels)
        
        # Record scores
        self.collector.record_histogram("hallucination_confidence", result.confidence_score, labels=labels)
        self.collector.record_histogram("source_coverage", result.source_coverage, labels=labels)
        self.collector.record_histogram("factual_consistency", result.factual_consistency, labels=labels)
    
    def record_safety_analysis(self, analysis: SafetyAnalysis, content_type: str):
        """Record metrics from safety analysis"""
        labels = {
            "content_type": content_type,
            "is_safe": str(analysis.is_safe),
            "risk_level": analysis.risk_level.value
        }
        
        self.collector.increment_counter("safety_analysis_total", labels=labels)
        
        if not analysis.is_safe:
            self.collector.increment_counter("safety_violations", labels=labels)
        
        # Record risk scores by category
        for category, score in analysis.risk_scores.items():
            category_labels = {**labels, "safety_category": category.value}
            self.collector.record_histogram("risk_score_by_category", score, labels=category_labels)
        
        # Record overall risk
        self.collector.record_histogram("overall_risk_score", analysis.overall_risk, labels=labels)
    
    def record_circuit_breaker_event(self, event_type: str, state: str):
        """Record circuit breaker events"""
        labels = {
            "event_type": event_type,
            "state": state
        }
        
        self.collector.increment_counter("circuit_breaker_events", labels=labels)
        
        if event_type == "triggered":
            self.collector.increment_counter("circuit_breaker_triggered", labels=labels)
    
    async def get_real_time_dashboard(self) -> Dict[str, Any]:
        """Get real-time safety dashboard data"""
        return {
            "current_metrics": self.collector.get_metrics_summary(time_window_minutes=5),
            "recent_alerts": self.collector.alerts[-10:],  # Last 10 alerts
            "circuit_breaker_status": "operational",  # Would get from actual service
            "timestamp": datetime.now().isoformat()
        }
    
    async def generate_comprehensive_report(self) -> Dict[str, Any]:
        """Generate comprehensive safety report"""
        return await self.analyzer.generate_safety_report()
    
    def get_alerts(self, hours: int = 24) -> List[Dict[str, Any]]:
        """Get recent alerts"""
        cutoff_time = datetime.now() - timedelta(hours=hours)
        return [
            alert for alert in self.collector.alerts
            if datetime.fromisoformat(alert["timestamp"]) >= cutoff_time
        ]
