gene_chart_margin = {top: 10, right: 30, bottom: 30, left: 80},
    gene_chart_margin_lower = {top: 5, right: gene_chart_margin.right, bottom: 5, left: gene_chart_margin.left},
    gene_chart_width = 1100 - gene_chart_margin.left - gene_chart_margin.right;

lower_gene_chart_height = 50 - gene_chart_margin_lower.top - gene_chart_margin_lower.bottom,
    gene_chart_height = 300 - gene_chart_margin.top - gene_chart_margin.bottom - lower_gene_chart_height - gene_chart_margin_lower.top - gene_chart_margin_lower.bottom;

function region_chart(data, variant_data) {
    var metric = 'mean';

    var x = d3.scale.linear()
        .domain([d3.min(data, function(d) { return d.start; }), d3.max(data, function(d) { return d.end; })])
        .range([0, gene_chart_width]);

    var max_cov = 1;
    if (metric === 'mean' || metric === 'median') {
        max_cov = d3.max(data, function(d) { return d[metric]; });
    }

    var y = d3.scale.linear()
        .domain([0, max_cov])
        .range([gene_chart_height, 0]);

    var xAxis = d3.svg.axis()
        .scale(x)
        .orient("bottom");

    var yAxis = d3.svg.axis()
        .scale(y)
        .orient("left");

    var svg = d3.select('#region_plot_container').append("svg")
        .attr("width", gene_chart_width + gene_chart_margin.left + gene_chart_margin.right)
        .attr("height", gene_chart_height + gene_chart_margin.top + gene_chart_margin.bottom)
        .append("g")
        .attr('id', 'inner_graph')
        .attr("transform", "translate(" + gene_chart_margin.left + "," + gene_chart_margin.top + ")");

    svg.selectAll("bar")
        .data(data)
        .enter()
        .append("rect")
        .attr('class', 'main_plot_bars')
        .style("fill", "steelblue")
        .attr("x", function(d) {
            return x(d.start);
        })
        .attr("width", function(d) {
            var length_in_bases = d.end - d.start + 1;
            var width_of_base = gene_chart_width/data.length;
            return length_in_bases * width_of_base;
        })
        .attr("y", function(d) {
            return y(d[metric]) || 0;
        })
        .attr("height", function(d) {
            return (gene_chart_height - y(d[metric])) || 0;
        });

    svg.append("g")
        .attr("class", "x axis")
        .attr("transform", "translate(0," + gene_chart_height + ")")
        .call(xAxis);

    svg.append("g")
        .attr("class", "y axis")
        .call(yAxis);

    var svg_outer = d3.select('#region_plot_container').append("svg")
        .attr("width", gene_chart_width + gene_chart_margin_lower.left + gene_chart_margin_lower.right)
        .attr("height", lower_gene_chart_height)
        .append("g")
        .attr('id', 'track')
        .attr("transform", "translate(" + gene_chart_margin_lower.left + "," + 0 + ")");

    var exon_color = "lightsteelblue";
    svg_outer.append("line")
        .attr("y1", lower_gene_chart_height/2)
        .attr("y2", lower_gene_chart_height/2)
        .attr("x1", 0)
        .attr("x2", x(d3.max(data, function(d) { return d.start; })))
        .attr("stroke-width", 1)
        .attr("stroke", exon_color);

    var start = d3.min(variant_data, function(d) { return d.pos; });
    var bounds = get_af_bounds(variant_data);
    var min_af = bounds[0];
    var max_af = bounds[1];
    var variant_size_scale = d3.scale.log()
        .domain([min_af, max_af])
        .range([2, lower_gene_chart_height/3]);

    var tip = d3.tip().attr('class', 'd3-tip').html(function(d) {
        if (d.major_consequence) {
            return d.major_consequence.replace('_variant', '').replace(/_/g, ' ');
        } else {
            return 'None';
        }
    });
    svg.call(tip);

    svg_outer.selectAll("bar")
        .data(variant_data)
        .enter()
        .append("a")
        .attr('class', 'track_variant_link')
        .attr("xlink:href", function(d, i) { return "/variant/" + d.chrom + "-" + d.pos + "-" + d.ref + "-" + d.alt; })
        .attr("data-toggle", "tooltip")
        .attr('category', function(d) {
            return d.category;
        })
        .on('mouseover', function(d) {
            $('#variant_' + d.variant_id).find('td').addClass('table_hover');
            tip.show(d);
        })
        .on('mouseout', function(d) {
            $('#variant_' + d.variant_id).find('td').removeClass('table_hover');
            tip.hide(d);
        })
        //Circle
//        .append("circle")
        //Ellipse
        .append("ellipse")
        .attr("class", function(d) {
            return "track_variant " + d.category;
        })
        .style("opacity", 0.5)
        .attr("cx", function(d) { return x(d.pos) })
        .attr("cy", lower_gene_chart_height/2)
        //Circle
//        .attr("r", function(d, i) { return variant_size_scale(d.allele_freq); })
        //Ellipse
        .attr("rx", 2)
        .attr("ry", function(d) {
            if (d.allele_freq == 0) {
                return 0;
            } else {
                return variant_size_scale(d.allele_freq);
            }
        });
}

function change_region_chart_metric(data, metric, container) {

    var max_cov = 1;
    if (metric === 'mean' || metric === 'median') {
        max_cov = d3.max(data, function(d) { return d[metric]; });
    }
    console.log(max_cov);

    var y = d3.scale.linear()
        .domain([0, max_cov])
        .range([gene_chart_height, 0]);

    var svg = d3.select(container).select('#inner_graph');

    svg.selectAll("rect")
        .data(data)
        .transition()
        .duration(500)
        .attr("y", function(d) { return y(d[metric]); })
        .attr("height", function(d) { return gene_chart_height - y(d[metric]); });

    var yAxis = d3.svg.axis()
        .scale(y)
        .orient("left");

    svg.select(".y.axis")
        .transition()
        .duration(200)
        .call(yAxis);

}


$(document).ready(function() {
    // Change coverage plot
    $('.coverage_metric_buttons').change(function () {
        var v = $(this).attr('id').replace('_covmet_button', '');
        $('.coverage_subcat_selectors').hide();
        if (v == 'covered') {
            $('#over_x_select_container').show();
            v = $('#over_x_select').val().replace('X', '');
        } else {
            $('#average_select_container').show();
            v = $("#average_select").val();
        }
        change_region_chart_metric(window.coverage_stats, v, '#region_plot_container');
    });
    $('#over_x_select').change(function () {
        change_region_chart_metric(window.coverage_stats, $(this).val().replace('X', ''), '#region_plot_container');
    });
    $('#average_select').change(function () {
        change_region_chart_metric(window.coverage_stats, $(this).val(), '#region_plot_container');
    });

    if (window.coverage_stats != null) {
        region_chart(window.coverage_stats, window.variants);
        update_variants();
    }

});
