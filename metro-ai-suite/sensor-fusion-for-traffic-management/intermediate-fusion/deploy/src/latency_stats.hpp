#pragma once

#include <cstddef>
#include <limits>
#include <ostream>
#include <iomanip>
#include <string>

namespace perfstats {

struct StageStats {
    double sum_ms{0.0};
    double min_ms{std::numeric_limits<double>::infinity()};
    double max_ms{0.0};
    std::size_t count{0};

    void reset()
    {
        sum_ms = 0.0;
        min_ms = std::numeric_limits<double>::infinity();
        max_ms = 0.0;
        count = 0;
    }

    void add(double ms)
    {
        sum_ms += ms;
        if (ms < min_ms)
            min_ms = ms;
        if (ms > max_ms)
            max_ms = ms;
        ++count;
    }

    double avg() const
    {
        return count == 0 ? 0.0 : (sum_ms / static_cast<double>(count));
    }

    bool has_samples() const
    {
        return count > 0;
    }
};

inline void print_stage(std::ostream &os, const std::string &name, const StageStats &s)
{
    if (!s.has_samples()) {
        os << name << "=n/a";
        return;
    }
    os << name << "=" << std::fixed << std::setprecision(3) << s.avg() << " ms";
}

struct LidarLatencyStats {
    StageStats preprocess;
    StageStats pfe;
    StageStats scatter;
    StageStats total;

    void reset()
    {
        preprocess.reset();
        pfe.reset();
        scatter.reset();
        total.reset();
    }

    void add(double pre_ms, double pfe_ms, double scatter_ms)
    {
        preprocess.add(pre_ms);
        pfe.add(pfe_ms);
        scatter.add(scatter_ms);
        total.add(pre_ms + pfe_ms + scatter_ms);
    }

    void print(std::ostream &os, const std::string &label = "lidar") const
    {
        const std::ios::fmtflags f = os.flags();
        const std::streamsize p = os.precision();
        os << "[perf] " << label << " avg_ms: ";
        print_stage(os, "pre", preprocess);
        os << ", ";
        print_stage(os, "pfe", pfe);
        os << ", ";
        print_stage(os, "scatter", scatter);
        os << ", ";
        print_stage(os, "total", total);
        os << " (samples=" << total.count << ")" << std::endl;
        os.flags(f);
        os.precision(p);
    }
};

struct CameraLatencyStats {
    StageStats geom;
    StageStats cam;
    StageStats bevpool;
    StageStats total;

    void reset()
    {
        geom.reset();
        cam.reset();
        bevpool.reset();
        total.reset();
    }

    void add(double geom_ms, double cam_ms, double bevpool_ms)
    {
        geom.add(geom_ms);
        cam.add(cam_ms);
        bevpool.add(bevpool_ms);
        total.add(geom_ms + cam_ms + bevpool_ms);
    }

    void print(std::ostream &os, const std::string &label = "camera_bev") const
    {
        const std::ios::fmtflags f = os.flags();
        const std::streamsize p = os.precision();
        os << "[perf] " << label << " avg_ms: ";
        print_stage(os, "geom", geom);
        os << ", ";
        print_stage(os, "cam", cam);
        os << ", ";
        print_stage(os, "bevpool", bevpool);
        os << ", ";
        print_stage(os, "total", total);
        os << " (samples=" << total.count << ")" << std::endl;
        os.flags(f);
        os.precision(p);
    }
};

struct FusionLatencyStats {
    StageStats fuser;
    StageStats head;
    StageStats post;
    StageStats total;

    void reset()
    {
        fuser.reset();
        head.reset();
        post.reset();
        total.reset();
    }

    void add(double fuser_ms, double head_ms, double post_ms)
    {
        fuser.add(fuser_ms);
        head.add(head_ms);
        post.add(post_ms);
        total.add(fuser_ms + head_ms + post_ms);
    }

    void print(std::ostream &os, const std::string &label = "fusion") const
    {
        const std::ios::fmtflags f = os.flags();
        const std::streamsize p = os.precision();
        os << "[perf] " << label << " avg_ms: ";
        print_stage(os, "fuser", fuser);
        os << ", ";
        print_stage(os, "head", head);
        os << ", ";
        print_stage(os, "post", post);
        os << ", ";
        print_stage(os, "total", total);
        os << " (samples=" << total.count << ")" << std::endl;
        os.flags(f);
        os.precision(p);
    }
};

struct PipelineLatencyStats {
    StageStats lidar;
    StageStats camera_bev;
    StageStats fusion;
    StageStats total;

    void reset()
    {
        lidar.reset();
        camera_bev.reset();
        fusion.reset();
        total.reset();
    }

    void add(double lidar_ms, double cam_ms, double fusion_ms)
    {
        lidar.add(lidar_ms);
        camera_bev.add(cam_ms);
        fusion.add(fusion_ms);
        total.add(lidar_ms + cam_ms + fusion_ms);
    }

    void print(std::ostream &os, const std::string &label = "pipeline") const
    {
        const std::ios::fmtflags f = os.flags();
        const std::streamsize p = os.precision();
        os << "[perf] " << label << " avg_ms: ";
        print_stage(os, "lidar", lidar);
        os << ", ";
        print_stage(os, "camera_bev", camera_bev);
        os << ", ";
        print_stage(os, "fusion", fusion);
        os << ", ";
        print_stage(os, "total", total);
        os << " (samples=" << total.count << ")" << std::endl;
        os.flags(f);
        os.precision(p);
    }
};

}  // namespace perfstats
