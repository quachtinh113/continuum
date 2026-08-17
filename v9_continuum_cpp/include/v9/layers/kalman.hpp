#pragma once

#include <cmath>

namespace v9 {

/**
 * @brief Bộ lọc Kalman 1D thích ứng dùng theo dõi cân bằng giá phiên Á (Asia Session).
 */
class KalmanFilterTracker {
public:
    double state_estimate{0.0}; // x_hat: Ước lượng trạng thái giá trung tâm
    double error_covariance{1.0}; // P: Ma trận hiệp phương sai sai số
    double process_variance{1e-5}; // Q: Nhiễu quá trình (mức độ biến động ngầm)
    double measurement_variance{1e-3}; // R: Nhiễu đo lường (Spread & Tick noise)
    bool is_initialized{false};

    KalmanFilterTracker(double q = 1e-5, double r = 1e-3)
        : process_variance(q), measurement_variance(r) {}

    /**
     * @brief Cập nhật bước lọc Kalman với một mức giá mới.
     * @param measurement Giá đóng nến mới nhất.
     * @return Giá trị trung tâm đã lọc (Smoothed Equilibrium Price).
     */
    double update(double measurement) {
        if (!is_initialized) {
            state_estimate = measurement;
            error_covariance = 1.0;
            is_initialized = true;
            return state_estimate;
        }

        // 1. Time Update (Dự báo - Prediction Step)
        double predicted_state = state_estimate;
        double predicted_covariance = error_covariance + process_variance;

        // 2. Measurement Update (Cập nhật - Correction Step)
        double kalman_gain = predicted_covariance / (predicted_covariance + measurement_variance);
        state_estimate = predicted_state + kalman_gain * (measurement - predicted_state);
        error_covariance = (1.0 - kalman_gain) * predicted_covariance;

        return state_estimate;
    }

    void reset() {
        state_estimate = 0.0;
        error_covariance = 1.0;
        is_initialized = false;
    }
};

} // namespace v9
