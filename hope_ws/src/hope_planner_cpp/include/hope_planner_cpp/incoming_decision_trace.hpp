#pragma once
#include "hope_planner_cpp/flight_state_v2.hpp"
#include <array>
#include <condition_variable>
#include <fstream>
#include <thread>

namespace hope_planner_cpp {
// Default-off decision evidence. File I/O runs only on the exporter thread.
// Saturation is reported as incomplete evidence, never silently overwritten.
struct IncomingDecision {
  std::uint64_t sequence = 0, generation = 0, revision = 0, semantic_epoch = 0;
  std::int64_t source_ns = 0, receipt_ns = 0;
  PlayState state = PlayState::INVALID, route = PlayState::INVALID;
  ClassificationStatus classification = ClassificationStatus::PROVISIONAL;
  HistoryContinuity continuity = HistoryContinuity::kUnknown;
  bool command_retained = false, source_fault = false;
  std::array<char, 32> phase{};
  std::array<char, 32> acquisition{};
  std::array<char, 128> reason{};
  std::array<std::uint64_t, 128> events{};
  std::size_t event_count = 0;
  bool events_truncated = false;
};
class IncomingDecisionTrace {
public:
  void configure(const std::string &path, std::size_t capacity = 8192) {
    if (path.empty())
      return;
    if (!capacity || capacity > 65536)
      throw std::invalid_argument("decision trace capacity");
    out_.open(path);
    if (!out_)
      throw std::invalid_argument("decision trace path");
    rows_.resize(capacity);
    enabled_ = true;
    out_ << "sequence\tsource_ns\treceipt_"
            "ns\tphase\tgeneration\trevision\tsemantic_epoch\tplay_"
            "state\tclassification\tcontinuity\troute\tcommand_"
            "retained\tsource_fault\treason\tacquisition\tevent_ids\n";
    worker_ = std::thread([this] { export_rows(); });
  }
  ~IncomingDecisionTrace() { close(); }
  bool enabled() const { return enabled_; }
  void record(const IncomingDecision &row) {
    if (!enabled_)
      return;
    std::lock_guard<std::mutex> lock(mutex_);
    ++offered_;
    if (row.events_truncated)
      ++truncated_events_;
    if (size_ == rows_.size()) {
      ++lost_;
      return;
    }
    rows_[(begin_ + size_) % rows_.size()] = row;
    ++size_;
    cv_.notify_one();
  }
  void close() {
    if (!enabled_)
      return;
    {
      std::lock_guard<std::mutex> lock(mutex_);
      stopping_ = true;
      cv_.notify_one();
    }
    if (worker_.joinable())
      worker_.join();
    out_ << "# offered=" << offered_ << " written=" << written_
         << " lost=" << lost_ << " events_truncated=" << truncated_events_
         << " complete="
         << (lost_ == 0 && truncated_events_ == 0 && out_.good()) << '\n';
    out_.flush();
    enabled_ = false;
  }

private:
  void export_rows() {
    for (;;) {
      IncomingDecision row;
      {
        std::unique_lock<std::mutex> lock(mutex_);
        cv_.wait(lock, [this] { return size_ || stopping_; });
        if (!size_ && stopping_)
          return;
        row = rows_[begin_];
        begin_ = (begin_ + 1) % rows_.size();
        --size_;
      }
      out_ << row.sequence << '\t' << row.source_ns << '\t' << row.receipt_ns
           << '\t' << row.phase.data() << '\t' << row.generation << '\t'
           << row.revision << '\t' << row.semantic_epoch << '\t'
           << name(row.state) << '\t' << static_cast<int>(row.classification)
           << '\t' << static_cast<int>(row.continuity) << '\t'
           << name(row.route) << '\t' << row.command_retained << '\t'
           << row.source_fault << '\t' << row.reason.data() << '\t'
           << row.acquisition.data() << '\t';
      for (std::size_t i = 0; i < row.event_count; ++i) {
        if (i)
          out_ << ',';
        out_ << row.events[i];
      }
      out_ << '\n';
      ++written_;
    }
  }
  bool enabled_ = false, stopping_ = false;
  std::ofstream out_;
  std::thread worker_;
  std::mutex mutex_;
  std::condition_variable cv_;
  std::vector<IncomingDecision> rows_;
  std::size_t begin_ = 0, size_ = 0, offered_ = 0, written_ = 0, lost_ = 0,
              truncated_events_ = 0;
};
} // namespace hope_planner_cpp
