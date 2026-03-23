#pragma once
#include <string>
#include <vector>

struct Task {
    int id;
    std::string title;
    std::string description;
    bool completed;
    int priority;
    std::string dueDate;
    std::vector<std::string> tags;
    std::string createdAt;
};
